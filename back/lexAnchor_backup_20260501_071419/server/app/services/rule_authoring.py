from __future__ import annotations

import hashlib
import re
from typing import Any


LEGAL_KEYWORDS = [
    "unlimited liability",
    "liability cap",
    "indemnify",
    "auto renewal",
    "automatic renewal",
    "governing law",
    "jurisdiction",
    "intellectual property",
    "work product",
    "customer data",
    "training data",
    "subprocessor",
    "confidentiality",
    "residual knowledge",
    "termination",
    "return data",
    "delete data",
    "payment due",
    "service credit",
    "audit right",
    "assignment",
    "insurance",
    "不可抗力",
    "无限责任",
    "责任上限",
    "自动续约",
    "管辖法律",
    "争议解决",
    "知识产权",
    "客户数据",
    "训练模型",
    "转委托",
    "分包商",
    "保密义务",
    "剩余知识",
    "终止",
    "返还数据",
    "删除数据",
    "付款期限",
    "服务抵扣",
    "审计权",
    "保险",
]

NEGATION_TERMS = [
    "unless approved in writing",
    "except with prior written consent",
    "does not apply",
    "shall not",
    "经书面同意",
    "另有约定",
    "不适用",
    "不构成",
    "除外",
]

CRITICAL_TERMS = ["unlimited liability", "无限责任", "data breach", "数据泄露", "indemnify", "赔偿"]
HIGH_TERMS = ["intellectual property", "知识产权", "customer data", "客户数据", "subprocessor", "分包商", "termination", "终止"]
LOW_TERMS = ["notice", "通知", "format", "格式"]


class RuleDraftGenerator:
    def generate(self, *, guide_text: str, rule_scope: str, scope_id: str, source_name: str | None = None, max_rules: int = 12) -> dict[str, Any]:
        source_text = self._normalize(guide_text)
        candidates = self._candidate_segments(source_text)
        rules: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for segment in candidates:
            keywords = self._keywords(segment)
            if not keywords:
                continue
            rule_id = self._rule_id(scope_id, segment, seen_ids)
            rules.append(self._build_rule(rule_id, segment, keywords, source_name))
            if len(rules) >= max_rules:
                break
        if not rules and source_text:
            fallback_segment = source_text[:240]
            rule_id = self._rule_id(scope_id, fallback_segment, seen_ids)
            rules.append(self._build_rule(rule_id, fallback_segment, self._fallback_keywords(fallback_segment), source_name))
        draft_digest = hashlib.sha256((source_text + rule_scope + scope_id).encode("utf-8")).hexdigest()[:16]
        return {
            "ok": True,
            "draft_id": f"rule_draft_{draft_digest}",
            "rule_scope": rule_scope,
            "scope_id": scope_id,
            "rules_count": len(rules),
            "rules": rules,
            "review_checklist": self._review_checklist(),
            "warnings": self._warnings(rules),
        }

    def _build_rule(self, rule_id: str, segment: str, keywords: list[str], source_name: str | None) -> dict[str, Any]:
        severity = self._severity(segment)
        rule_type = self._rule_type(segment)
        rule: dict[str, Any] = {
            "rule_id": rule_id,
            "name": self._name(segment),
            "enabled": False,
            "type": rule_type,
            "category": self._category(segment),
            "severity": severity,
            "description": segment,
            "why_it_matters": "Drafted from lawyer guidance and must be reviewed before activation.",
            "recommendation": self._recommendation(segment),
            "requires_llm": rule_type == "semantic",
            "confidence_base": 0.55 if rule_type == "semantic" else 0.72,
            "escalation": severity in {"critical", "high"},
            "source": {"type": "lawyer_guidance", "name": source_name or "inline_guide"},
            "draft_status": "needs_lawyer_review",
        }
        if rule_type == "missing":
            rule["trigger"] = {"required_any": keywords[:6]}
        else:
            rule["trigger"] = {"any": keywords[:8]}
            rule["negative_filter"] = {"enabled": True, "terms": NEGATION_TERMS, "window_chars": 60}
        return rule

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    @staticmethod
    def _candidate_segments(text: str) -> list[str]:
        raw_segments = re.split(r"(?<=[。！？.!?])\s+|[\n\r]+|[;；]", text)
        segments = []
        for raw_segment in raw_segments:
            segment = raw_segment.strip(" -\t")
            if 18 <= len(segment) <= 420:
                segments.append(segment)
        return segments

    @staticmethod
    def _keywords(segment: str) -> list[str]:
        lowered = segment.lower()
        keywords = [keyword for keyword in LEGAL_KEYWORDS if keyword.lower() in lowered]
        quoted = re.findall(r"[\"'“”‘’]([^\"'“”‘’]{2,60})[\"'“”‘’]", segment)
        keywords.extend(item.strip() for item in quoted if item.strip())
        if keywords:
            return list(dict.fromkeys(keywords))
        return RuleDraftGenerator._fallback_keywords(segment)

    @staticmethod
    def _fallback_keywords(segment: str) -> list[str]:
        ascii_phrases = re.findall(r"[A-Za-z][A-Za-z\-]+(?:\s+[A-Za-z][A-Za-z\-]+){0,3}", segment)
        chinese_phrases = re.findall(r"[\u4e00-\u9fff]{2,8}", segment)
        candidates = [phrase.strip() for phrase in ascii_phrases + chinese_phrases if len(phrase.strip()) >= 2]
        return list(dict.fromkeys(candidates))[:5]

    @staticmethod
    def _severity(segment: str) -> str:
        lowered = segment.lower()
        if any(term.lower() in lowered for term in CRITICAL_TERMS):
            return "critical"
        if any(term.lower() in lowered for term in HIGH_TERMS):
            return "high"
        if any(term.lower() in lowered for term in LOW_TERMS):
            return "low"
        return "medium"

    @staticmethod
    def _rule_type(segment: str) -> str:
        lowered = segment.lower()
        if any(term in lowered for term in ["must include", "must contain", "missing", "不得缺少", "必须包含", "应包括"]):
            return "missing"
        if any(term in lowered for term in ["ambiguous", "commercially reasonable", "sole discretion", "material", "语义", "合理", "重大", "单方决定"]):
            return "semantic"
        return "keyword"

    @staticmethod
    def _category(segment: str) -> str:
        lowered = segment.lower()
        if any(term in lowered for term in ["liability", "责任", "indemnify", "赔偿"]):
            return "liability"
        if any(term in lowered for term in ["data", "privacy", "数据", "隐私"]):
            return "data"
        if any(term in lowered for term in ["intellectual property", "ip", "知识产权"]):
            return "ip"
        if any(term in lowered for term in ["termination", "终止"]):
            return "termination"
        if any(term in lowered for term in ["payment", "付款", "费用"]):
            return "payment"
        return "general"

    @staticmethod
    def _name(segment: str) -> str:
        clipped = segment.strip()
        return clipped[:72] + ("..." if len(clipped) > 72 else "")

    @staticmethod
    def _recommendation(segment: str) -> str:
        if "建议" in segment or "recommend" in segment.lower():
            return segment
        return "Review this clause against the source guidance and decide whether to revise, accept, or escalate."

    @staticmethod
    def _rule_id(scope_id: str, segment: str, seen_ids: set[str]) -> str:
        clean_scope = re.sub(r"[^a-zA-Z0-9_]+", "_", scope_id.lower()).strip("_") or "custom"
        ascii_tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9]+", segment.lower())
        slug = "_".join(ascii_tokens[:4]) if ascii_tokens else hashlib.sha256(segment.encode("utf-8")).hexdigest()[:8]
        base_id = f"{clean_scope}.{slug}"
        rule_id = base_id
        suffix = 2
        while rule_id in seen_ids:
            rule_id = f"{base_id}_{suffix}"
            suffix += 1
        seen_ids.add(rule_id)
        return rule_id

    @staticmethod
    def _review_checklist() -> list[str]:
        return [
            "确认 rule_id 命名和规则归属范围是否正确。",
            "确认关键词不会过宽触发正常条款。",
            "补充或收窄 negative_filter，避免已授权/例外场景误报。",
            "确认 severity、category、escalation 是否符合团队风险口径。",
            "用至少一段命中文本和一段不应命中文本做回归测试。",
            "律师审核后再把 enabled 改为 true 并合入对应规则库。",
        ]

    @staticmethod
    def _warnings(rules: list[dict[str, Any]]) -> list[str]:
        warnings = ["Generated rules are disabled by default and require lawyer approval before activation."]
        if any(rule.get("type") == "semantic" for rule in rules):
            warnings.append("Some rules require semantic validation; keep them out of v0.1 profiles unless intentionally using v0.2+.")
        return warnings
