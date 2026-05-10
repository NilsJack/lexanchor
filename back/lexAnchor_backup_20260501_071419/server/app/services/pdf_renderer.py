from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import fitz

from app.services.layout_index import rects_for_location


class PdfRenderer:
    def render_annotated_pdf(self, input_pdf: str, result: dict[str, Any], layout_map: dict[str, Any], output_pdf: str) -> dict[str, Any]:
        findings = self._unique_findings(result)
        try:
            with fitz.open(input_pdf) as document:
                self._draw_page_annotations(document, findings, layout_map)
                self._insert_summary_page(document, result, findings)
                output_path = Path(output_pdf)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                document.save(output_path, garbage=3, deflate=True)
            return {"ok": True, "output_pdf": output_pdf}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _draw_page_annotations(self, document: fitz.Document, findings: list[dict[str, Any]], layout_map: dict[str, Any]) -> None:
        for finding in findings:
            if finding.get("status") != "confirmed" or finding.get("anchor_type") != "text":
                continue
            evidence = finding.get("evidence") if isinstance(finding.get("evidence"), dict) else {}
            rectangles_by_page = rects_for_location(evidence.get("location"), layout_map, padding=1.5)
            for page_num, rectangles in rectangles_by_page.items():
                if page_num >= len(document):
                    continue
                page = document[page_num]
                for rectangle in rectangles:
                    color = self._severity_color(str(finding.get("severity") or "medium"))
                    highlight = page.add_highlight_annot(rectangle)
                    highlight.set_colors(stroke=color)
                    highlight.set_opacity(0.22)
                    highlight.update()
                    border = page.add_rect_annot(rectangle)
                    border.set_colors(stroke=color)
                    border.set_border(width=0.7)
                    border.set_opacity(0.65)
                    border.set_info(content=f"{finding.get('rule_id', 'LexAnchor')} {finding.get('severity', '')}".strip())
                    border.update()

    def _insert_summary_page(self, document: fitz.Document, result: dict[str, Any], findings: list[dict[str, Any]]) -> None:
        visible = [finding for finding in findings if finding.get("status") != "suppressed"]
        if not visible and not result.get("context"):
            return
        page = document.new_page(0, width=595, height=842)
        text = "\n".join(self._summary_lines(result, visible))
        target = fitz.Rect(44, 44, 552, 812)
        try:
            page.insert_textbox(target, text, fontsize=10.5, fontname="china-s", color=(0, 0, 0), align=0)
        except Exception:
            page.insert_textbox(target, text, fontsize=10.5, fontname="helv", color=(0, 0, 0), align=0)

    def _summary_lines(self, result: dict[str, Any], findings: list[dict[str, Any]]) -> list[str]:
        summary = result.get("summary") or {}
        context = result.get("context") or {}
        rule_counts = Counter(str(finding.get("rule_id") or "unknown") for finding in findings)
        anchor_counts = Counter(str(finding.get("anchor_kind") or finding.get("anchor_type") or "unknown") for finding in findings)
        lines = [
            "LexAnchor v0.1 锚点审查摘要",
            "",
            "v0.1 锚点范围：Text Anchor / Missing Anchor / Risk Anchor / Context Anchor",
            f"确认锚点：{summary.get('total_confirmed', 0)}；重大：{summary.get('critical', 0)}；高：{summary.get('high', 0)}；缺失：{summary.get('missing', 0)}。",
            "",
            "Context Anchor",
            f"合同类型：{context.get('contract_type') or '未识别'}",
            f"语言：{context.get('language') or '未识别'}",
            f"适用法律：{context.get('governing_law') or '未识别'}",
            f"管辖/争议解决：{context.get('jurisdiction') or '未识别'}",
            "",
            "Anchor Counts",
        ]
        if anchor_counts:
            lines.extend(f"- {name}: {count}" for name, count in anchor_counts.most_common())
        else:
            lines.append("- 本次未形成显式锚点")
        lines.extend(["", "Rule Distribution"])
        if rule_counts:
            for rule_id, count in rule_counts.most_common(8):
                sample = next((finding for finding in findings if str(finding.get("rule_id")) == rule_id), {})
                lines.append(f"- {sample.get('rule_name') or rule_id}: {count}")
        else:
            lines.append("- 无规则命中")
        missing = [finding for finding in findings if finding.get("anchor_type") == "missing"]
        if missing:
            lines.extend(["", "Missing Anchors"])
            for item in missing[:8]:
                lines.append(f"- {item.get('rule_name')}: {item.get('recommendation') or ''}")
        lines.extend(["", "说明：本报告为规则驱动的法律初筛与证据定位，不构成最终法律意见。"])
        return lines

    @staticmethod
    def _unique_findings(result: dict[str, Any]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        seen: set[str] = set()
        for key in ("findings", "semantic_candidates", "suppressed_findings"):
            for item in result.get(key) or []:
                if not isinstance(item, dict):
                    continue
                finding_id = str(item.get("finding_id") or id(item))
                if finding_id in seen:
                    continue
                seen.add(finding_id)
                findings.append(item)
        return findings

    @staticmethod
    def _severity_color(severity: str) -> tuple[float, float, float]:
        if severity in {"critical", "high"}:
            return (1, 0, 0)
        if severity == "medium":
            return (1, 0.72, 0)
        return (0.1, 0.45, 1)
