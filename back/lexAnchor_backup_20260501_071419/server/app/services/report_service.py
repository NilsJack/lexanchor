from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ReportService:
    def __init__(self, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def persist_reports(self, job_id: str, result: dict[str, Any]) -> dict[str, str]:
        job_dir = self.artifacts_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        json_path = job_dir / "report.json"
        markdown_path = job_dir / "report.md"

        json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path.write_text(self.to_markdown(result), encoding="utf-8")

        return {
            "json_report_path": str(json_path),
            "markdown_report_path": str(markdown_path),
            "json_report_url": f"/api/v1/jobs/{job_id}/report.json",
            "markdown_report_url": f"/api/v1/jobs/{job_id}/report.md",
        }

    def to_markdown(self, result: dict[str, Any]) -> str:
        summary = result.get("summary") or {}
        document_info = result.get("document_info") or {}
        context = result.get("context") or {}
        findings = list(result.get("findings") or [])
        obligation_anchors = list(result.get("obligation_anchors") or [])
        relation_anchors = list(result.get("relation_anchors") or [])
        action_anchors = list(result.get("action_anchors") or [])
        semantic_candidates = list(result.get("semantic_candidates") or [])
        suppressed = list(result.get("suppressed_findings") or [])

        lines = [
            "# LexAnchor Review Report",
            "",
            f"Document: {document_info.get('file_name', 'unknown')}",
            f"Document ID: {document_info.get('document_id', 'unknown')}",
            "",
            "## Summary",
            "",
            f"- Critical: {summary.get('critical', 0)}",
            f"- High: {summary.get('high', 0)}",
            f"- Medium: {summary.get('medium', 0)}",
            f"- Low: {summary.get('low', 0)}",
            f"- Missing Anchors: {summary.get('missing', 0)}",
            f"- Semantic Candidates: {summary.get('semantic_candidates', 0)}",
            f"- Obligation Anchors: {summary.get('obligation_anchors', 0)}",
            f"- Relation Anchors: {summary.get('relation_anchors', 0)}",
            f"- Action Anchors: {summary.get('action_anchors', 0)}",
            f"- Escalations: {summary.get('escalations', 0)}",
            f"- Suppressed: {summary.get('suppressed', 0)}",
            "",
            "## Context",
            "",
            f"- Contract Type: {context.get('contract_type') or 'unknown'}",
            f"- Language: {context.get('language') or 'unknown'}",
            f"- Governing Law: {context.get('governing_law') or 'not detected'}",
            f"- Jurisdiction: {context.get('jurisdiction') or 'not detected'}",
            "",
            "## Confirmed Anchors",
            "",
        ]

        if not findings:
            lines.append("No confirmed anchors were found.")
        for finding in findings:
            lines.extend(self._finding_lines(finding))

        lines.extend(["", "## Obligation Anchors", ""])
        if not obligation_anchors:
            lines.append("No obligation anchors were found.")
        for finding in obligation_anchors:
            lines.extend(self._finding_lines(finding))

        lines.extend(["", "## Relation Anchors", ""])
        if not relation_anchors:
            lines.append("No relation anchors were found.")
        for finding in relation_anchors:
            lines.extend(self._finding_lines(finding))

        lines.extend(["", "## Action Anchors", ""])
        if not action_anchors:
            lines.append("No action anchors were proposed.")
        for action in action_anchors:
            lines.extend(self._action_lines(action))

        lines.extend(["", "## Semantic Candidates", ""])
        if not semantic_candidates:
            lines.append("No semantic candidates were found.")
        for finding in semantic_candidates:
            lines.extend(self._finding_lines(finding))

        if suppressed:
            lines.extend(["", "## Suppressed Findings", ""])
            for finding in suppressed:
                lines.extend(self._finding_lines(finding))

        lines.extend(["", "## Disclaimer", "", str(result.get("disclaimer") or "")])
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _finding_lines(finding: dict[str, Any]) -> list[str]:
        evidence = finding.get("evidence") or {}
        risk = finding.get("risk") or {}
        escalation = finding.get("escalation") or {}
        matched_text = evidence.get("matched_text") or "document-level absence"
        return [
            f"### {finding.get('finding_id')} {finding.get('rule_name')}",
            "",
            f"- Rule: {finding.get('rule_id')}",
            f"- Anchor: {finding.get('anchor_kind')} / {finding.get('anchor_type')}",
            f"- Severity: {finding.get('severity')}",
            f"- Status: {finding.get('status')}",
            f"- Confidence: {risk.get('confidence')}",
            f"- Escalation Required: {escalation.get('required')}",
            f"- Evidence: {matched_text}",
            f"- Recommendation: {finding.get('recommendation') or 'N/A'}",
            "",
        ]

    @staticmethod
    def _action_lines(action: dict[str, Any]) -> list[str]:
        return [
            f"### {action.get('action_id')} {action.get('title')}",
            "",
            f"- Source: {action.get('source_anchor_type')} / {action.get('source_id')}",
            f"- Type: {action.get('action_type')}",
            f"- Priority: {action.get('priority')}",
            f"- Owner Role: {action.get('owner_role')}",
            f"- Due Policy: {action.get('due_policy')}",
            f"- Status: {action.get('status')}",
            f"- Recommendation: {action.get('recommendation') or 'N/A'}",
            "",
        ]
