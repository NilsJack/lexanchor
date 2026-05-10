from __future__ import annotations

import importlib
import logging
import os
import re
from typing import Any

logger = logging.getLogger("LexAnchor.langextract_grounding")


def ground_items_with_langextract(
    text: str,
    items: list[dict],
    *,
    text_key: str = "text",
    default_model_id: str = "gemini-3-flash-preview",
    allow_network: bool | None = None,
) -> tuple[list[dict], dict]:
    records = [dict(item) for item in (items or []) if isinstance(item, dict)]
    if not records or not str(text or "").strip():
        return records, {"enabled": False, "reason": "empty_input", "grounded": 0}
    if not _langextract_enabled(allow_network):
        return records, {"enabled": False, "reason": "network_not_enabled", "grounded": 0}

    targets = _collect_targets(records, text_key)
    if not targets:
        return records, {"enabled": False, "reason": "empty_targets", "grounded": 0}

    try:
        lx = importlib.import_module("langextract")
        data = importlib.import_module("langextract.data")
        model_id = os.getenv("LANGEXTRACT_MODEL", default_model_id)
        result = lx.extract(
            text_or_documents=str(text),
            prompt_description=_build_prompt(targets),
            examples=_build_examples(data),
            model_id=model_id,
            api_key=os.getenv("LANGEXTRACT_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            max_char_buffer=int(os.getenv("LANGEXTRACT_MAX_CHAR_BUFFER", "3000")),
            temperature=0.0,
            batch_length=int(os.getenv("LANGEXTRACT_BATCH_LENGTH", "4")),
            max_workers=int(os.getenv("LANGEXTRACT_MAX_WORKERS", "2")),
            extraction_passes=int(os.getenv("LANGEXTRACT_PASSES", "1")),
            show_progress=False,
            resolver_params={"suppress_parse_errors": True},
            language_model_params=_language_model_params(),
        )
    except Exception as exc:
        logger.warning("LangExtract grounding skipped: %s", exc)
        return records, {"enabled": True, "ok": False, "error": str(exc), "grounded": 0}

    spans_by_target = _extract_grounded_spans(result, targets)
    grounded = 0
    for record in records:
        key = _normalize_target(record.get(text_key))
        spans = spans_by_target.get(key) or []
        if not spans:
            continue
        record["grounded_spans"] = [{"start": start, "end": end, "source": "langextract"} for start, end in spans]
        record["grounding_source"] = "langextract"
        grounded += 1
    return records, {"enabled": True, "ok": True, "grounded": grounded, "targets": len(targets), "model": model_id, "route": "network"}


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
    route = str(
        os.getenv("LANGEXTRACT_BACKEND_MODE")
        or os.getenv("LEXANCHOR_BACKEND_MODE")
        or "local"
    ).strip().lower()
    return route == "network" and has_key


def _collect_targets(records: list[dict], text_key: str) -> list[str]:
    targets = []
    seen = set()
    for record in records:
        target = str(record.get(text_key) or "").strip()
        key = _normalize_target(target)
        if not target or not key or key in seen:
            continue
        seen.add(key)
        targets.append(target)
    return targets


def _build_prompt(targets: list[str]) -> str:
    target_lines = "\n".join(f"- {target}" for target in targets)
    return (
        "Extract only exact occurrences of the listed target strings from the document. "
        "Do not infer new entities. Preserve the exact source text and provide grounding offsets.\n\n"
        f"Targets:\n{target_lines}"
    )


def _build_examples(data: Any) -> list[Any]:
    pii_text = "甲方：张三。乙方：北京甲科技有限公司。"
    anchor_text = "合同约定违约金为总价款的百分之十。"
    pii_interval = _char_interval(data, pii_text, "张三")
    anchor_interval = _char_interval(data, anchor_text, "违约金")
    return [
        data.ExampleData(
            text=pii_text,
            extractions=[
                data.Extraction(
                    extraction_class="target",
                    extraction_text="张三",
                    **({"char_interval": pii_interval} if pii_interval is not None else {}),
                )
            ],
        ),
        data.ExampleData(
            text=anchor_text,
            extractions=[
                data.Extraction(
                    extraction_class="target",
                    extraction_text="违约金",
                    **({"char_interval": anchor_interval} if anchor_interval is not None else {}),
                )
            ],
        ),
    ]


def _char_interval(data: Any, source_text: str, target: str) -> Any | None:
    interval_type = getattr(data, "CharInterval", None)
    if interval_type is None:
        return None
    start = source_text.index(target)
    return interval_type(start_pos=start, end_pos=start + len(target))


def _language_model_params() -> dict:
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


def _extract_grounded_spans(result: Any, targets: list[str]) -> dict[str, list[tuple[int, int]]]:
    target_keys = {_normalize_target(target) for target in targets}
    spans_by_target: dict[str, list[tuple[int, int]]] = {}
    documents = result if isinstance(result, list) else [result]
    for document in documents:
        for extraction in getattr(document, "extractions", []) or []:
            key = _normalize_target(getattr(extraction, "extraction_text", ""))
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


def _normalize_target(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return re.sub(r"\s+", "", raw)