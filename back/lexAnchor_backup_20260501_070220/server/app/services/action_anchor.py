from __future__ import annotations

from typing import Any


class ActionAnchorService:
    def apply(self, result: dict[str, Any], *, policy: str = "default") -> dict[str, Any]:
        policy_name = str(policy or "default").strip().lower()
        if policy_name in {"0", "false", "off", "disabled", "none"}:
            result["action_policy"] = {"enabled": False, "policy": "disabled"}
            result["action_anchors"] = []
            return result

        actions: list[dict[str, Any]] = []
        seen_sources: set[str] = set()
        for source in self._action_sources(result):
            source_key = self._source_key(source)
            if source_key in seen_sources:
                continue
            seen_sources.add(source_key)
            actions.append(self._build_action(source, policy_name, len(actions) + 1))

        result["action_anchors"] = actions
        result["action_queue"] = {
            "enabled": True,
            "queue_type": "legal_action",
            "item_count": len(actions),
            "items": [
                {
                    "action_id": action["action_id"],
                    "source_anchor_type": action["source_anchor_type"],
                    "source_id": action["source_id"],
                    "priority": action["priority"],
                    "owner_role": action["owner_role"],
                    "action_type": action["action_type"],
                    "status": action["status"],
                }
                for action in actions
            ],
        }
        result["action_policy"] = {"enabled": True, "policy": policy_name, "anchor_count": len(actions)}
        result.setdefault("summary", {})["action_anchors"] = len(actions)
        return result

    def _action_sources(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for escalation in result.get("escalation_anchors") or []:
            if isinstance(escalation, dict):
                sources.append({"kind": "escalation", "payload": escalation})
        for finding in result.get("findings") or []:
            if not isinstance(finding, dict) or finding.get("status") != "confirmed":
                continue
            if str(finding.get("severity") or "").lower() in {"critical", "high"}:
                sources.append({"kind": str(finding.get("anchor_type") or "finding"), "payload": finding})
        for obligation in result.get("obligation_anchors") or []:
            if isinstance(obligation, dict) and str(obligation.get("severity") or "").lower() in {"critical", "high"}:
                sources.append({"kind": "obligation", "payload": obligation})
        for relation in result.get("relation_anchors") or []:
            if isinstance(relation, dict) and str(relation.get("severity") or "").lower() in {"critical", "high"}:
                sources.append({"kind": "relation", "payload": relation})
        return sources

    @staticmethod
    def _source_key(source: dict[str, Any]) -> str:
        payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
        return f"{source.get('kind')}:{payload.get('escalation_id') or payload.get('finding_id') or payload.get('rule_id') or id(payload)}"

    def _build_action(self, source: dict[str, Any], policy: str, index: int) -> dict[str, Any]:
        payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
        source_kind = str(source.get("kind") or payload.get("anchor_type") or "finding")
        severity = str(payload.get("severity") or (payload.get("finding_snapshot") or {}).get("severity") or "medium").lower()
        priority = self._priority(source_kind, severity)
        action_type = self._action_type(source_kind, payload)
        title = self._title(source_kind, payload, action_type)
        recommendation = payload.get("recommendation") or (payload.get("finding_snapshot") or {}).get("recommendation") or "Review and decide the next legal action."
        return {
            "action_id": f"AA-{index:04d}",
            "anchor_type": "action",
            "anchor_kind": "Action Anchor",
            "status": "proposed",
            "policy": policy,
            "source_anchor_type": source_kind,
            "source_id": payload.get("escalation_id") or payload.get("finding_id"),
            "source_rule_id": payload.get("source_rule_id") or payload.get("rule_id"),
            "severity": severity,
            "priority": priority,
            "owner_role": "senior_legal_reviewer" if priority in {"p0", "p1"} else "legal_reviewer",
            "action_type": action_type,
            "title": title,
            "description": payload.get("description") or (payload.get("finding_snapshot") or {}).get("description") or title,
            "recommendation": recommendation,
            "due_policy": "same_business_day" if priority == "p0" else "next_business_day" if priority == "p1" else "standard_review_cycle",
            "requires_human_decision": True,
        }

    @staticmethod
    def _priority(source_kind: str, severity: str) -> str:
        if severity == "critical":
            return "p0"
        if severity == "high" or source_kind == "escalation":
            return "p1"
        return "p2"

    @staticmethod
    def _action_type(source_kind: str, payload: dict[str, Any]) -> str:
        if source_kind == "escalation":
            return "review_escalation"
        if source_kind == "obligation":
            return "confirm_obligation"
        if source_kind == "relation":
            return "review_clause_dependency"
        if source_kind in {"semantic", "semantic_candidate"}:
            return "validate_semantic_risk"
        if payload.get("anchor_type") == "missing":
            return "add_missing_clause"
        return "revise_clause"

    @staticmethod
    def _title(source_kind: str, payload: dict[str, Any], action_type: str) -> str:
        rule_name = payload.get("rule_name") or payload.get("source_rule_id") or payload.get("rule_id") or source_kind
        if action_type == "review_escalation":
            return f"Review escalation: {rule_name}"
        if action_type == "confirm_obligation":
            return f"Confirm obligation handling: {rule_name}"
        if action_type == "review_clause_dependency":
            return f"Review clause dependency: {rule_name}"
        if action_type == "add_missing_clause":
            return f"Add or revise missing clause: {rule_name}"
        if action_type == "validate_semantic_risk":
            return f"Validate semantic risk: {rule_name}"
        return f"Revise clause: {rule_name}"
