from __future__ import annotations

import re
from typing import Any


class RedactionService:
    PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "phone_cn": r"(?<!\d)1[3-9]\d{9}(?!\d)",
        "id_card_cn": r"(?<!\d)\d{17}[0-9Xx](?!\d)",
        "ssn_us": r"\b\d{3}-\d{2}-\d{4}\b",
        "bank_card_candidate": r"(?<!\d)\d{16,19}(?!\d)",
    }

    def redact_text(self, text: str, *, mask: str = "[REDACTED]", detect_names: bool = False) -> dict[str, Any]:
        source_text = str(text or "")
        findings = []
        for label, pattern in self.PATTERNS.items():
            for match in re.finditer(pattern, source_text):
                findings.append(
                    {
                        "type": label,
                        "text": match.group(0),
                        "location": {"start": match.start(), "end": match.end()},
                    }
                )

        if detect_names:
            findings.extend(self._detect_simple_chinese_names(source_text))

        findings.sort(key=lambda item: (item["location"]["start"], item["location"]["end"]))
        redacted_text = self._apply_redactions(source_text, findings, mask)
        summary: dict[str, int] = {}
        for finding in findings:
            label = str(finding.get("type") or "unknown")
            summary[label] = summary.get(label, 0) + 1
        return {"redacted_text": redacted_text, "findings": findings, "summary": summary}

    @staticmethod
    def _apply_redactions(text: str, findings: list[dict[str, Any]], mask: str) -> str:
        output_parts = []
        cursor = 0
        for finding in findings:
            location = finding.get("location") or {}
            start = int(location.get("start") or 0)
            end = int(location.get("end") or 0)
            if start < cursor or end <= start:
                continue
            output_parts.append(text[cursor:start])
            output_parts.append(mask)
            cursor = end
        output_parts.append(text[cursor:])
        return "".join(output_parts)

    @staticmethod
    def _detect_simple_chinese_names(text: str) -> list[dict[str, Any]]:
        findings = []
        for pattern in (r"(?:甲方|乙方|联系人|签署人)[：: ]*([\u4e00-\u9fff]{2,4})",):
            for match in re.finditer(pattern, text):
                findings.append(
                    {
                        "type": "person_name_candidate",
                        "text": match.group(1),
                        "location": {"start": match.start(1), "end": match.end(1)},
                    }
                )
        return findings
