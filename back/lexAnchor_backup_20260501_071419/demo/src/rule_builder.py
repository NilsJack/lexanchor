import os
import json
import yaml
import sys
from typing import List, Dict, Any
import requests

# 引用内部模块
sys.path.append(os.path.dirname(__file__))
from extractor import run_extractor
from llm_validator import LexSemanticValidator

class LexRuleBuilder:
    """
    AI 规则提取器：将律师编写的审查指南（PDF/Word）自动化转化为 LexAnchor 规则 YAML。
    """
    def __init__(self, projects_root: str):
        self.projects_root = projects_root
        # 复用 Validator 的军火库调度能力，但需要一个专门的规则提取 Prompt
        self.validator = LexSemanticValidator(projects_root)

    def build_rules_from_doc(self, guide_path: str, industry_id: str) -> Dict[str, Any]:
        """
        核心流程：读取 -> 压缩 -> 提取 -> 格式化
        """
        print(f"[*] 正在读取审查指南: {guide_path}")
        
        # 1. 提取原文
        extract_res = run_extractor(guide_path, self.projects_root)
        if not extract_res["ok"]:
            return {"ok": False, "error": f"指南读取失败: {extract_res['error']}"}
        
        guide_text = extract_res["markdown_content"]

        # 2. 调用最高级军火进行规则提炼
        print(f"[*] 启动 AI 规则提炼 (行业: {industry_id})...")
        prompt = self._build_extraction_prompt(guide_text, industry_id)
        
        # 借用 validator 的 _check_with_fallback 逻辑，但由于任务不同，我们手动调用 fallback
        # 这里为了简单直接，我们构造一个伪 task 传给 validator 的通用调用逻辑
        rules_json = self._extract_via_llm(prompt)
        
        if not rules_json:
            return {"ok": False, "error": "AI 未能生成有效的规则结构"}

        # 3. 存储为 YAML
        output_path = os.path.join(self.projects_root, "config", "industry_configs", f"{industry_id}.yaml")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        final_data = {
            "industry_id": industry_id,
            "industry_name": rules_json.get("industry_name", industry_id),
            "rules": rules_json.get("rules", [])
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(final_data, f, allow_unicode=True, sort_keys=False)
            
        return {
            "ok": True, 
            "output_path": output_path, 
            "rules_count": len(final_data["rules"]),
            "preview": [r.get("rule_id") for r in final_data["rules"][:5]]
        }

    def _extract_via_llm(self, prompt: str) -> Dict[str, Any]:
        """循环尝试军火库模型，直到拿到规则 JSON"""
        for config in self.validator.model_pool:
            try:
                # 构造符合适配器的请求
                print(f"[*] 尝试使用模型 {config['id']} 进行提取...")
                content = ""
                if config["provider"] == "google_studio":
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config['model']}:generateContent?key={config['api_key']}"
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"response_mime_type": "application/json", "temperature": 0.1}
                    }
                    res = requests.post(url, json=payload, proxies=self.validator.proxies, timeout=60).json()
                    content = res["candidates"][0]["content"]["parts"][0]["text"]
                elif config["provider"] in ["openai_generic", "together", "lm_studio"]:
                    url = f"{config['base_url'].rstrip('/')}/chat/completions"
                    headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
                    payload = {
                        "model": config["model"],
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"}
                    }
                    res = requests.post(url, headers=headers, json=payload, proxies=self.validator.proxies if "localhost" not in url else None, timeout=90).json()
                    content = res["choices"][0]["message"]["content"]
                
                if content:
                    return json.loads(content)
            except Exception as e:
                print(f"[-] 模型 {config['id']} 提取规则失败: {e}")
                continue
        return {}

    def _build_extraction_prompt(self, guide_text: str, industry_id: str) -> str:
        return f"""你是一位合同审查规则工程师。请根据提供的【合同审查指南/要点】文档，将其转化为 LexAnchor 规则库格式。

### 行业标识
{industry_id}

### 审查指南原文
\"\"\"
{guide_text}
\"\"\"

### 任务要求
1. **识别风险点**：从指南中提取核心的风险条款描述、判断依据和修改建议。
2. **关键词映射**：为每个风险点构思 3-5 个容易在合同原文中出现的【触发关键词】。
3. **否定抑制**：识别出哪些词会导致该风险点失效（如“除...外”、“经书面同意”）。
4. **研判分级**：如果该项风险仅靠关键词识别不准，需要深度语义理解，请将 `requires_llm` 设为 true。

### 输出格式 (严格 JSON)
{{
  "industry_name": "行业中文名",
  "rules": [
    {{
      "rule_id": "{industry_id}.风险唯一标识",
      "severity": "critical/high/medium/low",
      "keywords": ["关键词1", "关键词2"],
      "negation_trigger": ["抑制词1"],
      "requires_llm": bool,
      "recommendation": "修改建议内容"
    }}
  ]
}}
"""

if __name__ == "__main__":
    # 测试代码
    builder = LexRuleBuilder("workspace/TOOLS/LexAnchor")
    print("Rule Builder AI Engine Ready.")
