import os
import yaml
import re
import json
from typing import List, Dict, Any

class LexRuleEngine:
    """
    LexAnchor 规则主脑：负责多层规则加载、Keyword/Pattern/Missing 判定及否定抑制。
    """
    def __init__(self, projects_root: str):
        self.projects_root = projects_root
        self.base_config_path = os.path.join(projects_root, "config", "rules_v0.1.yaml")
        self.rules = []
        self.negation_terms = ["不适用", "不构成", "不承担", "不属于", "不应视为", "除", "之外", "except", "not apply", "shall not"]

    def load_rules(self, industry_id: str = None, org_id: str = None):
        """
        分层加载逻辑: Base -> Industry -> Org (后加载的覆盖先加载的)
        """
        # 1. Load Base
        if os.path.exists(self.base_config_path):
            with open(self.base_config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data:
                    self.rules = data.get("rules", [])

        # 2. Load Industry Overlay
        if industry_id:
            ind_path = os.path.join(self.projects_root, "config", "industry_configs", f"{industry_id}.yaml")
            if os.path.exists(ind_path):
                with open(ind_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data:
                        ind_rules = data.get("rules", [])
                        self._merge_rules(ind_rules)

        # 3. Load Org Override
        if org_id:
            org_path = os.path.join(self.projects_root, "config", "org_configs", f"{org_id}.yaml")
            if os.path.exists(org_path):
                with open(org_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data:
                        org_rules = data.get("rules", [])
                        self._merge_rules(org_rules)
        
        print(f"[+] 规则加载完成，共计 {len(self.rules)} 条有效规则。")

    def _merge_rules(self, new_rules: List[Dict]):
        """
        根据 rule_id 进行合并覆盖
        """
        existing_ids = {r["rule_id"]: i for i, r in enumerate(self.rules)}
        for nr in new_rules:
            rid = nr["rule_id"]
            if rid in existing_ids:
                self.rules[existing_ids[rid]] = nr
            else:
                self.rules.append(nr)

    def list_available_industries(self) -> List[str]:
        """
        列出所有已配置的行业规则标识
        """
        config_dir = os.path.join(self.projects_root, "config", "industry_configs")
        if not os.path.exists(config_dir):
            return []

        files = [f for f in os.listdir(config_dir) if f.endswith(".yaml")]
        return [f.replace(".yaml", "") for f in files]

    def scan_text(self, text: str) -> List[Dict[str, Any]]:
        """
        全文本扫描：执行 keyword, missing, semantic 判定。
        """
        findings = []
        
        for rule in self.rules:
            rule_type = rule.get("type", "keyword")
            
            # 1. Missing 类型 (全文扫描)
            if rule_type == "missing":
                required = rule.get("trigger", {}).get("required_any", [])
                found = False
                for req in required:
                    if req in text:
                        found = True
                        break
                if not found:
                    findings.append({
                        "rule_id": rule["rule_id"],
                        "rule_name": rule.get("name", rule["rule_id"]),
                        "category": rule.get("category", ""),
                        "severity": rule["severity"],
                        "anchor_type": "document_level",
                        "anchor_layer": "perception",
                        "anchor_kind": "Missing Anchor",
                        "escalation": bool(rule.get("escalation")),
                        "reason": rule["description"],
                        "recommendation": rule["recommendation"]
                    })

            # 2. Keyword / Semantic / Pattern 类型 (片段扫描)
            else:
                triggers = rule.get("trigger", {}).get("any", [])
                for trigger in triggers:
                    # 寻找所有匹配位置 (简单示例，暂不处理重叠)
                    for match in re.finditer(re.escape(trigger), text):
                        start, end = match.span()
                        
                        # 获取上下文窗口用于否定词检测
                        context_start = max(0, start - 40)
                        context_end = min(len(text), end + 40)
                        context_window = text[context_start:context_end]
                        
                        # 否定抑制逻辑
                        negated = False
                        found_neg_term = ""
                        for neg in self.negation_terms:
                            if neg in context_window:
                                negated = True
                                found_neg_term = neg
                                break
                        
                        finding = {
                            "rule_id": rule["rule_id"],
                            "rule_name": rule.get("name", rule["rule_id"]),
                            "category": rule.get("category", ""),
                            "severity": rule["severity"],
                            "anchor_type": "text_span" if not rule.get("requires_llm") else "evidence_span",
                            "anchor_layer": "perception" if not rule.get("requires_llm") else "interpretation",
                            "anchor_kind": "Text Anchor" if not rule.get("requires_llm") else "Semantic Anchor",
                            "matched_text": trigger,
                            "location": {"start": start, "end": end},
                            "context": context_window.replace("\n", " "),
                            "requires_llm": rule.get("requires_llm", False),
                            "negation_flag": negated,
                            "escalation": bool(rule.get("escalation")),
                            "reason": rule.get("description", ""),
                            "recommendation": rule["recommendation"]
                        }
                        
                        if negated:
                            finding["status"] = "suppressed"
                            finding["negation_term"] = found_neg_term
                        
                        findings.append(finding)
                        
        return findings

if __name__ == "__main__":
    engine = LexRuleEngine("workspace/TOOLS/LexAnchor")
    engine.load_rules(industry_id="construction")
    
    # 测试扫描刚刚提取的装修文本
    with open("workspace/TOOLS/LexAnchor/data/gold_dataset/deco_sample_raw.md", "r") as f:
        content = f.read()
    
    results = engine.scan_text(content)
    
    # 分类预览
    doc_level = [r for r in results if r["anchor_type"] == "document_level"]
    text_spans = [r for r in results if r["anchor_type"] == "text_span" and r.get("status") != "suppressed"]
    suppressed = [r for r in results if r.get("status") == "suppressed"]
    semantics = [r for r in results if r.get("requires_llm")]

    print(f"\n[*] 扫描报告:")
    print(f"    - 结构缺失项: {len(doc_level)}")
    print(f"    - 关键词命中: {len(text_spans)}")
    print(f"    - 否定抑制项: {len(suppressed)}")
    print(f"    - 需LLM复核: {len(semantics)}")

    print(f"\n[*] 关键词命中示例:")
    for r in text_spans[:2]:
        print(f"      - [{r['rule_id']}] 命中: \"{r['matched_text']}\"")
        print(f"        上下文: ...{r['context']}...")

    if suppressed:
        print(f"\n[*] 否定抑制示例:")
        for r in suppressed[:1]:
            print(f"      - [{r['rule_id']}] 匹配 \"{r['matched_text']}\" 但被 \"{r['negation_term']}\" 抑制")
