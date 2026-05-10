from __future__ import annotations

import importlib
import logging
import os
import re
from typing import Any

logger = logging.getLogger("LexAnchor.langextract_grounding")


class LangExtractGroundingService:
    def ground_result(self, text: str, result: dict[str, Any], *, allow_network: bool | None = None) -> dict[str, Any]:
        records = self._collect_records(result)
        targets = [record for record in records if str(record.get("target_text") or "").strip()]
        if not targets:
            result["grounding"] = {"enabled": False, "reason": "empty_targets", "grounded": 0}
            return result

        grounded_targets, meta = self._ground_items_with_langextract(text, targets, allow_network=allow_network)
        if not meta.get("ok"):
            grounded_targets, meta = self._ground_items_locally(text, targets, prior_meta=meta)

        grounded_by_id = {item.get("record_id"): item for item in grounded_targets if item.get("grounded_spans")}
        grounded_count = 0
        for finding in self._all_findings(result):
            record_id = finding.get("finding_id")
            grounded = grounded_by_id.get(record_id)
            if not grounded:
                continue
            first_span = grounded["grounded_spans"][0]
            evidence = finding.setdefault("evidence", {})
            previous_location = evidence.get("location")
            evidence["location"] = {"start": int(first_span["start"]), "end": int(first_span["end"])}
            if previous_location and previous_location != evidence["location"]:
                evidence["fallback_location"] = previous_location
            evidence["grounding_source"] = first_span.get("source") or grounded.get("grounding_source")
            evidence["grounded_spans"] = grounded["grounded_spans"]
            grounded_count += 1

        meta["grounded"] = grounded_count
        result["grounding"] = meta
        return result

    def _ground_items_with_langextract(
        self,
        text: str,
        items: list[dict[str, Any]],
        *,
        allow_network: bool | None = None,
        default_model_id: str = "gemini-3-flash-preview",
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        records = [dict(item) for item in items]
        if not records or not str(text or "").strip():
            return records, {"enabled": False, "reason": "empty_input", "ok": False, "grounded": 0}
        if not self._langextract_enabled(allow_network):
            return records, {"enabled": False, "reason": "network_not_enabled", "ok": False, "grounded": 0}

        targets = self._collect_target_strings(records)
        if not targets:
            return records, {"enabled": False, "reason": "empty_targets", "ok": False, "grounded": 0}

        try:
            langextract = importlib.import_module("langextract")
            data = importlib.import_module("langextract.data")
            model_id = os.getenv("LANGEXTRACT_MODEL", default_model_id)
            result = langextract.extract(
                text_or_documents=str(text),
                prompt_description=self._build_prompt(targets),
                examples=self._build_examples(data),
                model_id=model_id,
                api_key=os.getenv("LANGEXTRACT_API_KEY") or os.getenv("GOOGLE_API_KEY"),
                max_char_buffer=int(os.getenv("LANGEXTRACT_MAX_CHAR_BUFFER", "3000")),
                temperature=0.0,
                batch_length=int(os.getenv("LANGEXTRACT_BATCH_LENGTH", "4")),
                max_workers=int(os.getenv("LANGEXTRACT_MAX_WORKERS", "2")),
                extraction_passes=int(os.getenv("LANGEXTRACT_PASSES", "1")),
                show_progress=False,
                resolver_params={"suppress_parse_errors": True},
                language_model_params=self._language_model_params(),
            )
        except Exception as exc:
            logger.warning("LangExtract grounding skipped: %s", exc)
            return records, {"enabled": True, "ok": False, "error": str(exc), "grounded": 0, "provider": "langextract"}

        spans_by_target = self._extract_grounded_spans(result, targets)
        grounded = 0
        for record in records:
            key = self._normalize_target(record.get("target_text"))
            spans = spans_by_target.get(key) or []
            if not spans:
                continue
            record["grounded_spans"] = [{"start": start, "end": end, "source": "langextract"} for start, end in spans]
            record["grounding_source"] = "langextract"
            grounded += 1
        return records, {"enabled": True, "ok": True, "grounded": grounded, "targets": len(targets), "model": model_id, "provider": "langextract"}

    def _ground_items_locally(
        self,
        text: str,
        items: list[dict[str, Any]],
        *,
        prior_meta: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        records = [dict(item) for item in items]
        grounded = 0
        for record in records:
            target = str(record.get("target_text") or "").strip()
            if not target:
                continue
            start = self._local_start(text, target, record.get("preferred_start"))
            if start < 0:
                continue
            record["grounded_spans"] = [{"start": start, "end": start + len(target), "source": "local_exact"}]
            record["grounding_source"] = "local_exact"
            grounded += 1
        meta = {
            "enabled": True,
            "ok": True,
            "provider": "local_exact",
            "grounded": grounded,
            "targets": len(records),
        }
        if prior_meta:
            meta["langextract"] = prior_meta
        return records, meta

    @staticmethod
    def _local_start(text: str, target: str, preferred_start: Any = None) -> int:
        try:
            start_hint = int(preferred_start)
        except Exception:
            start_hint = -1
        if start_hint >= 0:
            exact = text.find(target, max(0, start_hint - 25))
            if exact >= 0:
                return exact
        return text.find(target)

    @classmethod
    def _collect_records(cls, result: dict[str, Any]) -> list[dict[str, Any]]:
        records = []
        for finding in cls._all_findings(result):
            evidence = finding.get("evidence") or {}
            if finding.get("anchor_scope") == "document":
                continue
            target_text = str(evidence.get("matched_text") or "").strip()
            if not target_text:
                continue
            location = evidence.get("location") if isinstance(evidence.get("location"), dict) else {}
            records.append(
                {
                    "record_id": finding.get("finding_id"),
                    "target_text": target_text,
                    "preferred_start": location.get("start"),
                }
            )
        return records

    @staticmethod
    def _all_findings(result: dict[str, Any]) -> list[dict[str, Any]]:
        findings = []
        for key in ("findings", "semantic_candidates", "suppressed_findings"):
            findings.extend(item for item in result.get(key, []) if isinstance(item, dict))
        return findings

    @staticmethod
    def _langextract_enabled(allow_network: bool | None = None) -> bool:
        flag = str(os.getenv("LANGEXTRACT_ENABLED", "auto")).strip().lower()
        if flag in {"0", "false", "no", "off", "disabled"}:
            return False
        if flag in {"1", "true", "yes", "on", "enabled", "force"}:
            return True
        if allow_network is False:
            return False
        has_key = bool(os.getenv("LANGEXTRACT_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        if allow_network is True:
            return has_key
        route = str(os.getenv("LANGEXTRACT_BACKEND_MODE") or os.getenv("LEXANCHOR_BACKEND_MODE") or "local").strip().lower()
        return route == "network" and has_key

    @staticmethod
    def _collect_target_strings(records: list[dict[str, Any]]) -> list[str]:
        targets = []
        seen = set()
        for record in records:
            target = str(record.get("target_text") or "").strip()
            key = LangExtractGroundingService._normalize_target(target)
            if not target or not key or key in seen:
                continue
            seen.add(key)
            targets.append(target)
        return targets

    @staticmethod
    def _build_prompt(targets: list[str]) -> str:
        target_lines = "\n".join(f"- {target}" for target in targets)
        return (
            "Extract only exact occurrences of the listed target strings from the document. "
            "Do not infer new entities. Preserve exact source text and provide grounding offsets.\n\n"
            f"Targets:\n{target_lines}"
        )

    @staticmethod
    def _build_examples(data: Any) -> list[Any]:
        source_text = "合同约定违约金为总价款的百分之十。"
        interval = LangExtractGroundingService._char_interval(data, source_text, "违约金")
        return [
            data.ExampleData(
                text=source_text,
                extractions=[
                    data.Extraction(
                        extraction_class="target",
                        extraction_text="违约金",
                        **({"char_interval": interval} if interval is not None else {}),
                    )
                ],
            )
        ]

    @staticmethod
    def _char_interval(data: Any, source_text: str, target: str) -> Any | None:
        interval_type = getattr(data, "CharInterval", None)
        if interval_type is None:
            return None
        start = source_text.index(target)
        return interval_type(start_pos=start, end_pos=start + len(target))

    @staticmethod
    def _language_model_params() -> dict[str, Any]:
        params: dict[str, Any] = {}
        timeout = os.getenv("LANGEXTRACT_TIMEOUT")
        if timeout:
            try:
                params["http_options"] = {"timeout": float(timeout)}
            except ValueError:
                pass
        retries = os.getenv("LANGEXTRACT_MAX_RETRIES")
        if retries:
            try:
                params["max_retries"] = int(retries)
            except ValueError:
                pass
        return params

    @staticmethod
    def _extract_grounded_spans(result: Any, targets: list[str]) -> dict[str, list[tuple[int, int]]]:
        target_keys = {LangExtractGroundingService._normalize_target(target) for target in targets}
        spans_by_target: dict[str, list[tuple[int, int]]] = {}
        documents = result if isinstance(result, list) else [result]
        for document in documents:
            for extraction in getattr(document, "extractions", []) or []:
                key = LangExtractGroundingService._normalize_target(getattr(extraction, "extraction_text", ""))
                if key not in target_keys:
                    continue
                interval = getattr(extraction, "char_interval", None)
                start = getattr(interval, "start_pos", None)
                end = getattr(interval, "end_pos", None)
                if start is None or end is None:
                    continue
                try:
                    span = (int(start), int(end))
                except Exception:
                    continue
                if span[1] <= span[0]:
                    continue
                spans_by_target.setdefault(key, [])
                if span not in spans_by_target[key]:
                    spans_by_target[key].append(span)
        return spans_by_target

    @staticmethod
    def _normalize_target(value: Any) -> str:
        raw = str(value or "").strip().lower()
        return re.sub(r"\s+", "", raw)
