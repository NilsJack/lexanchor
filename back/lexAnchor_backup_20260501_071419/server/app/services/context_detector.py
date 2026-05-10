from __future__ import annotations

import re
from typing import Any


class ContextDetector:
    def detect(self, text: str) -> dict[str, Any]:
        source = str(text or "")
        return {
            "contract_type": self._detect_contract_type(source),
            "language": self._detect_language(source),
            "governing_law": self._extract_governing_law(source),
            "jurisdiction": self._extract_jurisdiction(source),
            "party_names": self._extract_party_names(source),
        }

    def context_anchors(self, text: str) -> list[dict[str, Any]]:
        anchors = []
        for context_type, pattern in (
            ("governing_law", r"governed by the laws of ([A-Za-z ,.-]+)"),
            ("jurisdiction", r"jurisdiction of ([A-Za-z ,.-]+)"),
            ("governing_law", r"适用法律[为是：: ]*([^。；\n]+)"),
            ("jurisdiction", r"(?:管辖|争议解决)[为是：: ]*([^。；\n]+)"),
        ):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                anchors.append(
                    {
                        "context_id": f"C-{len(anchors) + 1:04d}",
                        "anchor_type": "context",
                        "context_type": context_type,
                        "value": match.group(1).strip(),
                        "confidence": 0.72,
                        "evidence": {
                            "matched_text": match.group(0).strip(),
                            "location": {"start": match.start(), "end": match.end()},
                        },
                    }
                )
        return anchors

    @staticmethod
    def _detect_language(text: str) -> str:
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        ascii_letters = len(re.findall(r"[A-Za-z]", text))
        if chinese_chars and chinese_chars >= ascii_letters / 3:
            return "zh"
        if ascii_letters:
            return "en"
        return "unknown"

    @staticmethod
    def _detect_contract_type(text: str) -> str:
        lowered = text.lower()
        if "saas" in lowered or "software as a service" in lowered:
            return "saas_vendor"
        if "装修" in text or "工程" in text or "construction" in lowered:
            return "construction"
        if "non-disclosure" in lowered or "保密" in text:
            return "nda"
        return "contract"

    @staticmethod
    def _extract_governing_law(text: str) -> str | None:
        patterns = [
            r"governed by the laws of ([A-Za-z ,.-]+)",
            r"适用法律[为是：: ]*([^。；\n]+)",
        ]
        return ContextDetector._first_group(text, patterns)

    @staticmethod
    def _extract_jurisdiction(text: str) -> str | None:
        patterns = [
            r"jurisdiction of ([A-Za-z ,.-]+)",
            r"(?:管辖|争议解决)[为是：: ]*([^。；\n]+)",
        ]
        return ContextDetector._first_group(text, patterns)

    @staticmethod
    def _extract_party_names(text: str) -> list[str]:
        parties = []
        for pattern in (r"甲方[：: ]*([^\n。；]+)", r"乙方[：: ]*([^\n。；]+)"):
            match = re.search(pattern, text)
            if match:
                parties.append(match.group(1).strip())
        return parties[:6]

    @staticmethod
    def _first_group(text: str, patterns: list[str]) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip().rstrip(".")
        return None
