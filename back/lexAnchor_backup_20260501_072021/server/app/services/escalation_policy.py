from __future__ import annotations

from copy import deepcopy
from typing import Any


class EscalationPolicyService:
    def apply(self, result: dict[str, Any], *, policy: str = "default") -> dict[str, Any]:
        policy_name = str(policy or "default").strip().lower()
        if policy_name in {"0", "false", "off", "disabled", "none"}:
            result["escalation_policy"] = {"enabled": False, "policy": "disabled"}
            result["escalation_anchors"] = []
            return result

        anchors: list[dict[str, Any]] = []
        candidates = list(result.get("findings") or []) + list(result.get("semantic_candidates") or [])
        for finding in candidates:
            if finding.get("status") not in {"confirmed", "needs_validation"}:
                continue
            reasons = self._reasons_for(finding, policy_name)
            if not reasons:
                continue
            anchors.append(self._build_anchor(finding, reasons, policy_name, len(anchors) + 1))

        result["escalation_anchors"] = anchors
        result["review_queue"] = {
            "enabled": True,
            "queue_type": "legal_review",
            "item_count": len(anchors),
            "items": [
                {
                    "escalation_id": anchor["escalation_id"],
                    "source_finding_id": anchor["source_finding_id"],
                    "priority": anchor["priority"],
                    "route": anchor["route"],
                    "reasons": anchor["reasons"],
                }
                for anchor in anchors
            ],
        }
        result["escalation_policy"] = {"enabled": True, "policy": policy_name, "anchor_count": len(anchors)}
        result.setdefault("summary", {})["escalations"] = len(anchors)
        return result

    def _reasons_for(self, finding: dict[str, Any], policy: str) -> list[str]:
        reasons: list[str] = []
        severity = str(finding.get("severity") or "medium").lower()
        anchor_type = str(finding.get("anchor_type") or "")
        risk = finding.get("risk") if isinstance(finding.get("risk"), dict) else {}
        escalation = finding.get("escalation") if isinstance(finding.get("escalation"), dict) else {}

        if escalation.get("required"):
            reasons.append("explicit_rule_escalation")
        if severity == "critical":
            reasons.append("critical_severity")
        if severity == "high" and risk.get("human_review_needed"):
            reasons.append("high_severity_human_review")
        if anchor_type == "missing" and severity in {"critical", "high"}:
            reasons.append("missing_required_clause")
        if anchor_type == "semantic_candidate":
            reasons.append("semantic_uncertainty")
        if anchor_type == "semantic" and risk.get("human_review_needed"):
            reasons.append("confirmed_semantic_review")
        if policy == "strict" and severity == "medium" and risk.get("human_review_needed"):
            reasons.append("strict_policy_medium_review")

        deduplicated: list[str] = []
        for reason in reasons:
            if reason not in deduplicated:
                deduplicated.append(reason)
        return deduplicated

    @staticmethod
    def _build_anchor(finding: dict[str, Any], reasons: list[str], policy: str, index: int) -> dict[str, Any]:
        severity = str(finding.get("severity") or "medium").lower()
        priority = "p0" if severity == "critical" else "p1" if severity == "high" else "p2"
        route = "senior_legal_review" if priority in {"p0", "p1"} else "legal_review"
        return {
            "escalation_id": f"EA-{index:04d}",
            "anchor_type": "escalation",
            "anchor_kind": "Escalation Anchor",
            "status": "open",
            "policy": policy,
            "source_finding_id": finding.get("finding_id"),
            "source_rule_id": finding.get("rule_id"),
            "source_anchor_type": finding.get("anchor_type"),
            "severity": severity,
            "priority": priority,
            "route": route,
            "reasons": reasons,
            "finding_snapshot": deepcopy(finding),
        }
