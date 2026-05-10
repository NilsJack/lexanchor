from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.anchor_engine import DEFAULT_NEGATION_TERMS


class SemanticValidatorService:
    def validate_result(self, result: dict[str, Any], *, mode: str = "candidate") -> dict[str, Any]:
        validation_mode = str(mode or "candidate").strip().lower()
        if validation_mode in {"0", "false", "off", "disabled", "none"}:
            result["semantic_validation"] = {"enabled": False, "mode": "disabled"}
            return result
        if validation_mode not in {"validate", "validated", "local"}:
            result["semantic_validation"] = {"enabled": False, "mode": "candidate"}
            result.setdefault("semantic_anchors", [])
            result.setdefault("dismissed_semantic_candidates", [])
            return result

        candidates = list(result.get("semantic_candidates") or [])
        confirmed: list[dict[str, Any]] = []
        dismissed: list[dict[str, Any]] = []
        remaining: list[dict[str, Any]] = []

        for candidate in candidates:
            validation = self._validate_candidate(candidate)
            if validation["status"] == "confirmed":
                confirmed.append(self._promote_candidate(candidate, validation, len(confirmed) + 1))
            elif validation["status"] == "dismissed":
                dismissed.append(self._dismiss_candidate(candidate, validation))
            else:
                remaining.append(candidate)

        existing_findings = list(result.get("findings") or [])
        result["findings"] = existing_findings + confirmed
        result["semantic_anchors"] = confirmed
        result["semantic_candidates"] = remaining
        result["dismissed_semantic_candidates"] = dismissed
        result["semantic_validation"] = {
            "enabled": True,
            "mode": "local",
            "provider": "local_semantic_validator",
            "prompt_version": "lexanchor-semantic-v0.2-local",
            "candidate_count": len(candidates),
            "confirmed_count": len(confirmed),
            "dismissed_count": len(dismissed),
        }
        result["summary"] = self._recalculate_summary(result)
        return result

    def _validate_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        evidence = candidate.get("evidence") if isinstance(candidate.get("evidence"), dict) else {}
        context = str(evidence.get("context") or evidence.get("matched_text") or "")
        matched_text = str(evidence.get("matched_text") or "").strip()
        negation = self._negation_term(context)
        if negation:
            return {
                "status": "dismissed",
                "reason": "semantic_negation_detected",
                "negation_term": negation,
                "confidence": 0.2,
            }
        if not matched_text:
            return {"status": "needs_validation", "reason": "missing_span_evidence", "confidence": 0.0}
        base_confidence = float((candidate.get("risk") or {}).get("confidence") or 0.5)
        severity = str(candidate.get("severity") or "medium").lower()
        severity_boost = 0.15 if severity in {"critical", "high"} else 0.05 if severity == "medium" else 0.0
        confidence = min(0.92, max(0.55, base_confidence + severity_boost))
        return {
            "status": "confirmed",
            "reason": "local_rule_context_supports_semantic_risk",
            "confidence": confidence,
            "evidence_spans": [matched_text],
        }

    @staticmethod
    def _promote_candidate(candidate: dict[str, Any], validation: dict[str, Any], index: int) -> dict[str, Any]:
        finding = deepcopy(candidate)
        finding["finding_id"] = f"SA-{index:04d}"
        finding["anchor_type"] = "semantic"
        finding["anchor_kind"] = "Semantic Anchor"
        finding["status"] = "confirmed"
        finding["included_in_summary_score"] = True
        finding["human_review_needed"] = True
        finding["semantic_validation"] = validation
        finding.setdefault("risk", {})["confidence"] = float(validation.get("confidence") or finding.get("risk", {}).get("confidence") or 0.5)
        finding.setdefault("risk", {})["human_review_needed"] = True
        finding["render"] = {"strategy": "semantic_highlight", "color": "purple"}
        return finding

    @staticmethod
    def _dismiss_candidate(candidate: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
        finding = deepcopy(candidate)
        finding["status"] = "dismissed"
        finding["included_in_summary_score"] = False
        finding["semantic_validation"] = validation
        return finding

    @staticmethod
    def _negation_term(context: str) -> str | None:
        lowered_context = context.lower()
        for term in DEFAULT_NEGATION_TERMS:
            term_text = str(term or "").strip()
            if term_text and term_text.lower() in lowered_context:
                return term_text
        return None

    @staticmethod
    def _recalculate_summary(result: dict[str, Any]) -> dict[str, int]:
        summary = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "missing": 0,
            "semantic_candidates": len(result.get("semantic_candidates") or []),
            "semantic_anchors": 0,
            "obligation_anchors": 0,
            "relation_anchors": 0,
            "dismissed_semantic_candidates": len(result.get("dismissed_semantic_candidates") or []),
            "suppressed": len(result.get("suppressed_findings") or []),
            "escalations": 0,
            "total_confirmed": 0,
        }
        for finding in result.get("findings") or []:
            if finding.get("status") != "confirmed" or finding.get("included_in_summary_score") is False:
                continue
            severity = str(finding.get("severity") or "medium").lower()
            if severity in summary:
                summary[severity] += 1
            if finding.get("anchor_type") == "missing":
                summary["missing"] += 1
            if finding.get("anchor_type") == "semantic":
                summary["semantic_anchors"] += 1
            if finding.get("anchor_type") == "obligation":
                summary["obligation_anchors"] += 1
            if finding.get("anchor_type") == "relation":
                summary["relation_anchors"] += 1
            if (finding.get("escalation") or {}).get("required"):
                summary["escalations"] += 1
            summary["total_confirmed"] += 1
        return summary
