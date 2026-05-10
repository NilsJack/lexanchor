from __future__ import annotations

import hashlib
import re
from typing import Any

from app.services.anchor_capabilities import anchor_enabled, resolve_anchor_capabilities
from app.services.context_detector import ContextDetector
from app.services.rule_loader import RuleLoader


DEFAULT_NEGATION_TERMS = [
    "不适用",
    "不构成",
    "不承担",
    "不属于",
    "不应视为",
    "除",
    "之外",
    "except",
    "not apply",
    "does not apply",
    "shall not",
    "not constitute",
]

SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}


class AnchorEngine:
    def __init__(self, rule_loader: RuleLoader, context_detector: ContextDetector | None = None) -> None:
        self.rule_loader = rule_loader
        self.context_detector = context_detector or ContextDetector()

    def scan_text(
        self,
        text: str,
        *,
        ruleset: str = "rules_v0.1",
        industry_id: str | None = None,
        org_id: str | None = None,
        document_info: dict[str, Any] | None = None,
        anchor_profile: str | None = None,
        enabled_anchors: str | list[str] | None = None,
    ) -> dict[str, Any]:
        source_text = str(text or "")
        capabilities = resolve_anchor_capabilities(ruleset=ruleset, anchor_profile=anchor_profile, enabled_anchors=enabled_anchors)
        rules = self.rule_loader.load_rules(ruleset=ruleset, industry_id=industry_id, org_id=org_id)
        findings = self._scan_rules(source_text, rules, capabilities)
        context = self.context_detector.detect(source_text) if anchor_enabled(capabilities, "context") else {}
        context_anchors = self.context_detector.context_anchors(source_text) if anchor_enabled(capabilities, "context") else []
        summary = self._build_summary(findings)
        document = self._document_info(source_text, document_info)

        return {
            "version": capabilities["version"],
            "product": "LexAnchor",
            "mode": "contract_scan",
            "document_info": document,
            "anchor_capabilities": capabilities,
            "ruleset": {
                "name": ruleset,
                "industry_id": industry_id,
                "org_id": org_id,
                "rule_count": len(rules),
            },
            "context": context,
            "summary": summary,
            "findings": [finding for finding in findings if finding.get("status") == "confirmed"],
            "missing_anchors": [finding for finding in findings if finding.get("anchor_type") == "missing" and finding.get("status") == "confirmed"],
            "obligation_anchors": [finding for finding in findings if finding.get("anchor_type") == "obligation" and finding.get("status") == "confirmed"],
            "relation_anchors": [finding for finding in findings if finding.get("anchor_type") == "relation" and finding.get("status") == "confirmed"],
            "semantic_candidates": [finding for finding in findings if finding.get("anchor_type") == "semantic_candidate"],
            "suppressed_findings": [finding for finding in findings if finding.get("status") == "suppressed"],
            "context_anchors": context_anchors,
            "artifacts": {},
            "disclaimer": "This result is a rule-driven first-pass legal review aid and does not constitute final legal advice.",
        }

    def _scan_rules(self, text: str, rules: list[dict[str, Any]], capabilities: dict[str, Any]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        counters = {"F": 0, "M": 0, "S": 0, "O": 0, "R": 0, "X": 0}

        for rule in rules:
            rule_type = str(rule.get("type") or "keyword").strip().lower()
            if rule_type == "missing":
                if not anchor_enabled(capabilities, "missing"):
                    continue
                missing_finding = self._scan_missing_rule(text, rule, counters)
                if missing_finding:
                    findings.append(missing_finding)
                continue

            if rule_type == "obligation":
                if not anchor_enabled(capabilities, "obligation"):
                    continue
                findings.extend(self._scan_typed_span_rule(text, rule, counters, anchor_type="obligation", anchor_layer="extraction", anchor_kind="Obligation Anchor", counter_key="O"))
                continue

            if rule_type == "relation":
                if not anchor_enabled(capabilities, "relation"):
                    continue
                relation_finding = self._scan_relation_rule(text, rule, counters)
                if relation_finding:
                    findings.append(relation_finding)
                continue

            if self._rule_requires_semantic(rule) and not anchor_enabled(capabilities, "semantic_candidate"):
                continue

            if not self._rule_requires_semantic(rule) and not anchor_enabled(capabilities, "text"):
                continue

            if rule_type == "pattern":
                findings.extend(self._scan_pattern_rule(text, rule, counters))
                continue

            findings.extend(self._scan_keyword_rule(text, rule, counters))

        return findings

    def _scan_missing_rule(self, text: str, rule: dict[str, Any], counters: dict[str, int]) -> dict[str, Any] | None:
        required_terms = list((rule.get("trigger") or {}).get("required_any") or [])
        lowered_text = text.lower()
        found = any(str(term).lower() in lowered_text for term in required_terms if str(term).strip())
        if found:
            return None

        counters["M"] += 1
        return self._build_finding(
            finding_id=f"M-{counters['M']:04d}",
            rule=rule,
            anchor_type="missing",
            anchor_layer="perception",
            anchor_kind="Missing Anchor",
            status="confirmed",
            evidence={"matched_text": None, "trigger": None, "location": None, "required_any": required_terms},
            confidence=rule.get("confidence_base", 0.95),
            included_in_summary_score=True,
        )

    def _scan_pattern_rule(self, text: str, rule: dict[str, Any], counters: dict[str, int]) -> list[dict[str, Any]]:
        regex_patterns = list((rule.get("trigger") or {}).get("regex") or [])
        findings: list[dict[str, Any]] = []
        for regex_pattern in regex_patterns:
            try:
                matches = re.finditer(str(regex_pattern), text, flags=re.IGNORECASE | re.MULTILINE)
            except re.error:
                continue
            for match in matches:
                findings.append(self._span_finding(text, rule, match.group(0), regex_pattern, match.start(), match.end(), counters))
        return findings

    def _scan_keyword_rule(self, text: str, rule: dict[str, Any], counters: dict[str, int]) -> list[dict[str, Any]]:
        triggers = list((rule.get("trigger") or {}).get("any") or [])
        findings: list[dict[str, Any]] = []
        for trigger in triggers:
            trigger_text = str(trigger or "").strip()
            if not trigger_text:
                continue
            for match in re.finditer(re.escape(trigger_text), text, flags=re.IGNORECASE):
                findings.append(self._span_finding(text, rule, match.group(0), trigger_text, match.start(), match.end(), counters))
        return findings

    def _scan_typed_span_rule(
        self,
        text: str,
        rule: dict[str, Any],
        counters: dict[str, int],
        *,
        anchor_type: str,
        anchor_layer: str,
        anchor_kind: str,
        counter_key: str,
    ) -> list[dict[str, Any]]:
        triggers = list((rule.get("trigger") or {}).get("any") or [])
        findings: list[dict[str, Any]] = []
        for trigger in triggers:
            trigger_text = str(trigger or "").strip()
            if not trigger_text:
                continue
            for match in re.finditer(re.escape(trigger_text), text, flags=re.IGNORECASE):
                findings.append(
                    self._typed_span_finding(
                        text,
                        rule,
                        match.group(0),
                        trigger_text,
                        match.start(),
                        match.end(),
                        counters,
                        anchor_type=anchor_type,
                        anchor_layer=anchor_layer,
                        anchor_kind=anchor_kind,
                        counter_key=counter_key,
                    )
                )
        return findings

    def _scan_relation_rule(self, text: str, rule: dict[str, Any], counters: dict[str, int]) -> dict[str, Any] | None:
        trigger = rule.get("trigger") if isinstance(rule.get("trigger"), dict) else {}
        required_terms = list(trigger.get("requires_all") or [])
        lowered_text = text.lower()
        spans: list[dict[str, Any]] = []
        for term in required_terms:
            term_text = str(term or "").strip()
            if not term_text:
                continue
            start = lowered_text.find(term_text.lower())
            if start < 0:
                return None
            spans.append({"text": text[start : start + len(term_text)], "start": start, "end": start + len(term_text)})
        if not spans:
            return None

        counters["R"] += 1
        relation = rule.get("relation") if isinstance(rule.get("relation"), dict) else {}
        finding = self._build_finding(
            finding_id=f"R-{counters['R']:04d}",
            rule=rule,
            anchor_type="relation",
            anchor_layer="graph",
            anchor_kind="Relation Anchor",
            status="confirmed",
            evidence={"matched_text": None, "trigger": required_terms, "location": None, "related_spans": spans},
            confidence=rule.get("confidence_base", 0.7),
            included_in_summary_score=True,
        )
        finding["anchor_scope"] = "cross_clause"
        finding["relation"] = {
            "relation_type": relation.get("type") or rule.get("relation_type") or "dependency",
            "source": relation.get("source") or (required_terms[0] if required_terms else None),
            "target": relation.get("target") or (required_terms[-1] if required_terms else None),
            "direction": relation.get("direction") or "source_to_target",
        }
        return finding

    def _span_finding(
        self,
        text: str,
        rule: dict[str, Any],
        matched_text: str,
        trigger: str,
        start: int,
        end: int,
        counters: dict[str, int],
    ) -> dict[str, Any]:
        requires_llm = self._rule_requires_semantic(rule)
        anchor_type = "semantic_candidate" if requires_llm else "text"
        anchor_layer = "interpretation" if requires_llm else "perception"
        anchor_kind = "Semantic Anchor" if requires_llm else "Text Anchor"
        status = "needs_validation" if requires_llm else "confirmed"
        included_in_summary_score = not requires_llm
        context_window = self._context_window(text, start, end, rule)
        negation_term = self._negation_term(context_window, rule)

        if negation_term and not requires_llm:
            status = "suppressed"
            included_in_summary_score = False

        counter_key = "S" if requires_llm else "F"
        if status == "suppressed":
            counter_key = "X"
        counters[counter_key] += 1

        finding = self._build_finding(
            finding_id=f"{counter_key}-{counters[counter_key]:04d}",
            rule=rule,
            anchor_type=anchor_type,
            anchor_layer=anchor_layer,
            anchor_kind=anchor_kind,
            status=status,
            evidence={
                "matched_text": matched_text,
                "trigger": trigger,
                "location": {"start": start, "end": end},
                "context": context_window,
            },
            confidence=rule.get("confidence_base", 0.5 if requires_llm else 0.9),
            included_in_summary_score=included_in_summary_score,
        )
        if negation_term and status == "suppressed":
            finding["suppressed_reason"] = "negation_filter"
            finding["negation_term"] = negation_term
        if requires_llm:
            finding["human_review_needed"] = True
        return finding

    def _typed_span_finding(
        self,
        text: str,
        rule: dict[str, Any],
        matched_text: str,
        trigger: str,
        start: int,
        end: int,
        counters: dict[str, int],
        *,
        anchor_type: str,
        anchor_layer: str,
        anchor_kind: str,
        counter_key: str,
    ) -> dict[str, Any]:
        context_window = self._context_window(text, start, end, rule)
        negation_term = self._negation_term(context_window, rule)
        status = "suppressed" if negation_term else "confirmed"
        active_counter_key = "X" if status == "suppressed" else counter_key
        counters[active_counter_key] += 1
        finding = self._build_finding(
            finding_id=f"{active_counter_key}-{counters[active_counter_key]:04d}",
            rule=rule,
            anchor_type=anchor_type,
            anchor_layer=anchor_layer,
            anchor_kind=anchor_kind,
            status=status,
            evidence={"matched_text": matched_text, "trigger": trigger, "location": {"start": start, "end": end}, "context": context_window},
            confidence=rule.get("confidence_base", 0.75),
            included_in_summary_score=status == "confirmed",
        )
        if negation_term:
            finding["suppressed_reason"] = "negation_filter"
            finding["negation_term"] = negation_term
        return finding

    def _build_finding(
        self,
        *,
        finding_id: str,
        rule: dict[str, Any],
        anchor_type: str,
        anchor_layer: str,
        anchor_kind: str,
        status: str,
        evidence: dict[str, Any],
        confidence: float,
        included_in_summary_score: bool,
    ) -> dict[str, Any]:
        severity = str(rule.get("severity") or "medium").lower()
        escalation_required = bool(rule.get("escalation")) or severity in {"critical", "high"}
        human_review_needed = escalation_required or anchor_type in {"missing", "semantic_candidate"}
        render_strategy = self._render_strategy(anchor_type)
        return {
            "finding_id": finding_id,
            "rule_id": rule.get("rule_id"),
            "rule_name": rule.get("name") or rule.get("rule_id"),
            "category": rule.get("category"),
            "anchor_type": anchor_type,
            "anchor_layer": anchor_layer,
            "anchor_kind": anchor_kind,
            "anchor_scope": "document" if anchor_type == "missing" else "cross_clause" if anchor_type == "relation" else "span",
            "status": status,
            "severity": severity,
            "included_in_summary_score": included_in_summary_score,
            "risk": {
                "risk_type": rule.get("risk_type") or rule.get("category") or "general",
                "severity": severity,
                "confidence": float(confidence),
                "human_review_needed": human_review_needed,
            },
            "escalation": {
                "required": escalation_required,
                "reason": "explicit_rule_or_high_severity" if escalation_required else "not_required_by_v0_1_policy",
            },
            "evidence": evidence,
            "description": rule.get("description", ""),
            "why_it_matters": rule.get("why_it_matters", ""),
            "recommendation": rule.get("recommendation", ""),
            "render": render_strategy,
        }

    @staticmethod
    def _context_window(text: str, start: int, end: int, rule: dict[str, Any]) -> str:
        filter_config = rule.get("negative_filter") if isinstance(rule.get("negative_filter"), dict) else {}
        window_chars = int(filter_config.get("window_chars") or 40)
        context_start = max(0, start - window_chars)
        context_end = min(len(text), end + window_chars)
        return text[context_start:context_end].replace("\n", " ")

    @staticmethod
    def _negation_term(context_window: str, rule: dict[str, Any]) -> str | None:
        filter_config = rule.get("negative_filter") if isinstance(rule.get("negative_filter"), dict) else {}
        if filter_config.get("enabled") is False:
            return None
        terms = filter_config.get("terms") or DEFAULT_NEGATION_TERMS
        lowered_context = context_window.lower()
        for term in terms:
            term_text = str(term or "").strip()
            if term_text and term_text.lower() in lowered_context:
                return term_text
        return None

    @staticmethod
    def _rule_requires_semantic(rule: dict[str, Any]) -> bool:
        return bool(rule.get("requires_llm") or str(rule.get("type") or "").strip().lower() == "semantic")

    @staticmethod
    def _render_strategy(anchor_type: str) -> dict[str, Any]:
        if anchor_type == "missing":
            return {"strategy": "summary_card", "color": "orange"}
        if anchor_type == "semantic_candidate":
            return {"strategy": "report_only", "color": "gray"}
        if anchor_type == "obligation":
            return {"strategy": "highlight_text", "color": "blue"}
        if anchor_type == "relation":
            return {"strategy": "relation_card", "color": "green"}
        return {"strategy": "highlight_text", "color": "red"}

    @staticmethod
    def _build_summary(findings: list[dict[str, Any]]) -> dict[str, int]:
        summary = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "missing": 0,
            "semantic_candidates": 0,
            "obligation_anchors": 0,
            "relation_anchors": 0,
            "suppressed": 0,
            "escalations": 0,
            "total_confirmed": 0,
        }
        for finding in findings:
            status = finding.get("status")
            anchor_type = finding.get("anchor_type")
            if status == "suppressed":
                summary["suppressed"] += 1
                continue
            if anchor_type == "semantic_candidate":
                summary["semantic_candidates"] += 1
                continue
            if status != "confirmed" or finding.get("included_in_summary_score") is False:
                continue
            severity = str(finding.get("severity") or "medium").lower()
            if severity in summary:
                summary[severity] += 1
            if anchor_type == "missing":
                summary["missing"] += 1
            if anchor_type == "obligation":
                summary["obligation_anchors"] += 1
            if anchor_type == "relation":
                summary["relation_anchors"] += 1
            if (finding.get("escalation") or {}).get("required"):
                summary["escalations"] += 1
            summary["total_confirmed"] += 1
        return summary

    @staticmethod
    def _document_info(text: str, document_info: dict[str, Any] | None) -> dict[str, Any]:
        info = dict(document_info or {})
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        info.setdefault("document_id", f"doc_{digest}")
        info.setdefault("file_name", "inline_text.txt")
        info.setdefault("file_type", "text")
        info.setdefault("char_count", len(text))
        return info
