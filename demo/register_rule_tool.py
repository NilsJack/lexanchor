import os
import sys

# 自动定位项目根目录并加入路径
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.abspath(os.path.join(current_dir, "../../../"))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from core.tool_registry import ToolRegistry
import yaml

# 增加入口封装
def run(industry_id: str, guide_path: str = None, **kwargs):
    """
    阿郎工具箱入口：将审查指南转为行业规则 YAML。
    用户只需说行业名和给文件，路径由工具自动处理。
    """
    if not guide_path:
        # 如果用户只说了行业没给文件，可以从 kwargs 找
        guide_path = kwargs.get("file_path")
        
    if not guide_path:
        return {"ok": False, "error": "请提供审查指南文档（PDF/Word/Markdown）。"}

    sys.path.append(os.path.dirname(__file__))
    from src.rule_builder import LexRuleBuilder
    builder = LexRuleBuilder("workspace/TOOLS/LexAnchor")
    
    # 模糊匹配逻辑同步
    industry_map = {"装修": "construction", "工程": "construction", "IT": "it_service"}
    final_id = industry_map.get(industry_id, industry_id)
    
    return builder.build_rules_from_doc(guide_path, final_id)


def run_tool(args: dict | None = None):
    payload = args if isinstance(args, dict) else {}
    industry_id = payload.get("industry_id") or payload.get("industry") or ""
    guide_path = payload.get("guide_path") or payload.get("file_path") or payload.get("input_file")
    extras = dict(payload)
    for key in ("industry_id", "industry", "guide_path", "file_path", "input_file"):
        extras.pop(key, None)
    return run(industry_id=industry_id, guide_path=guide_path, **extras)


def main(args: dict | None = None):
    return run_tool(args)

def register():
    registry = ToolRegistry()
    tool_id = "lex_rule_extractor_tool"
    tool_dir = "workspace/TOOLS/LexAnchor"
    
    registry.register_tool(
        tool_id=tool_id,
        name="LexAnchor 行业规则提取器",
        path=tool_dir,
        entrypoint="register_rule_tool.py", 
        kind="python",
        desc="AI 规则工厂。只需提供行业名称和律师审查指南文件，即可自动生成该行业的审查规则库。路径自动处理，无需用户干预。",
        tags=["legal", "ai", "config", "rule"]
    )

    # 注册参数定义：极简版
    reg_data = registry._load()
    for tool in reg_data["tools"]:
        if tool["id"] == tool_id:
            tool["parameters"] = {
                "industry_id": {
                    "type": "string",
                    "description": "你想创建/更新的行业名称（如 '装修', 'IT', 'finance'）",
                    "required": True
                },
                "guide_path": {
                    "type": "string",
                    "description": "审查指南文档路径",
                    "required": True
                }
            }
            tool["usage"] = "阿郎，根据这个文件生成 [industry_id] 行业的审查规则：[guide_path]"
            tool["examples"] = [
                "根据 playbook.pdf 生成‘金融租赁’行业的规则",
                "提取‘装修’行业规则：samples/guide.docx"
            ]
    registry._save(reg_data)
    print(f"✅ {tool_id} 极简接口已就绪！")

if __name__ == "__main__":
    register()
