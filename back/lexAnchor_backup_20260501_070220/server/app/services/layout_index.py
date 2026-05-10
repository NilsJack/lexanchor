from __future__ import annotations

import os
import re
from typing import Any

import fitz


def build_pdf_layout_map(input_file: str, extracted_text: str | None = None, pages_ocr_data: dict | None = None) -> dict:
    text_basis = str(extracted_text or "")
    layout_map = {
        "version": 2,
        "source_format": "pdf",
        "original_pdf_path": os.path.abspath(input_file),
        "offset_basis": "extracted_text",
        "pages": [],
    }
    native_text = ""
    with fitz.open(input_file) as document:
        for page_num, page in enumerate(document):
            page_text = page.get_text()
            page_start = len(native_text)
            native_text += page_text
            layout_map["pages"].append(_build_native_page_layout(page, page_num, page_text, page_start))
    if pages_ocr_data:
        layout_map["pages_ocr_data"] = pages_ocr_data
        _attach_ocr_offsets(layout_map, text_basis, pages_ocr_data)
    return layout_map


def rects_for_location(location: Any, layout_map: dict | None, *, padding: float = 1.5) -> dict[int, list[fitz.Rect]]:
    span = _parse_location_span(location)
    if span is None or not isinstance(layout_map, dict):
        return {}
    return rects_for_span(layout_map, span[0], span[1], padding=padding)


def rects_for_span(layout_map: dict | None, start: int, end: int, *, padding: float = 1.5) -> dict[int, list[fitz.Rect]]:
    if not isinstance(layout_map, dict) or start is None or end is None or end <= start:
        return {}
    grouped: dict[int, list[fitz.Rect]] = {}
    seen: set[tuple[int, int, int, int, int]] = set()
    for page in layout_map.get("pages") or []:
        try:
            page_num = int(page.get("page_num"))
        except Exception:
            continue
        for line in list(page.get("lines") or []) + list(page.get("ocr_lines") or []):
            line_start, line_end = _span_bounds(line)
            if line_start is None or line_end is None or not _overlaps(start, end, line_start, line_end):
                continue
            token_rects = _token_rects_for_span(line, start, end, padding)
            rects = token_rects or [_rect_from_bbox(line.get("bbox"), padding)]
            for rect in rects:
                if rect is None or rect.is_empty or rect.is_infinite:
                    continue
                key = _rect_key(page_num, rect)
                if key in seen:
                    continue
                seen.add(key)
                grouped.setdefault(page_num, []).append(rect)
    return grouped


def _build_native_page_layout(page: fitz.Page, page_num: int, page_text: str, page_start: int) -> dict:
    page_layout = {
        "page_num": page_num,
        "char_start": page_start,
        "char_end": page_start + len(page_text),
        "width": float(page.rect.width),
        "height": float(page.rect.height),
        "lines": [],
    }
    text_dict = page.get_text("dict")
    search_cursor = 0
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            spans = [span for span in line.get("spans", []) if str(span.get("text") or "")]
            line_text = "".join(str(span.get("text") or "") for span in spans)
            if not line_text.strip():
                continue
            local_start = page_text.find(line_text, search_cursor)
            if local_start < 0:
                local_start = page_text.find(line_text.strip(), search_cursor)
            if local_start < 0:
                continue
            search_cursor = local_start + max(len(line_text), 1)
            line_start = page_start + local_start
            record = {
                "text": line_text,
                "char_start": line_start,
                "char_end": line_start + len(line_text),
                "bbox": list(line.get("bbox") or []),
                "spans": [],
            }
            span_cursor = 0
            for span in spans:
                span_text = str(span.get("text") or "")
                span_local = line_text.find(span_text, span_cursor)
                if span_local < 0:
                    continue
                span_cursor = span_local + len(span_text)
                record["spans"].append(
                    {
                        "text": span_text,
                        "char_start": line_start + span_local,
                        "char_end": line_start + span_local + len(span_text),
                        "bbox": list(span.get("bbox") or []),
                    }
                )
            page_layout["lines"].append(record)
    return page_layout


def _attach_ocr_offsets(layout_map: dict, extracted_text: str, pages_ocr_data: dict) -> None:
    pages = layout_map.setdefault("pages", [])
    while len(pages) < len(pages_ocr_data):
        page_num = len(pages)
        pages.append({"page_num": page_num, "char_start": 0, "char_end": 0, "lines": []})
    cursor = 0
    for raw_page_num in sorted(pages_ocr_data.keys(), key=lambda item: int(item)):
        page_num = int(raw_page_num)
        if page_num >= len(pages):
            pages.append({"page_num": page_num, "char_start": 0, "char_end": 0, "lines": []})
        ocr_lines = []
        for line in pages_ocr_data.get(raw_page_num) or []:
            line_text = str((line or {}).get("text") or "")
            if not line_text.strip():
                continue
            start = extracted_text.find(line_text, cursor)
            if start < 0:
                start = extracted_text.find(line_text)
            if start < 0:
                continue
            end = start + len(line_text)
            cursor = max(cursor, end)
            record = dict(line)
            record["char_start"] = start
            record["char_end"] = end
            record["tokens"] = _attach_token_offsets(line_text, start, line.get("tokens") or [])
            ocr_lines.append(record)
        pages[page_num]["ocr_lines"] = ocr_lines


def _attach_token_offsets(line_text: str, line_start: int, tokens: list) -> list:
    out = []
    cursor = 0
    for token in tokens:
        if not isinstance(token, dict):
            continue
        token_text = str(token.get("text") or "")
        if not token_text:
            continue
        local = line_text.find(token_text, cursor)
        if local < 0:
            local = line_text.find(token_text)
        record = dict(token)
        if local >= 0:
            cursor = local + len(token_text)
            record["char_start"] = line_start + local
            record["char_end"] = line_start + local + len(token_text)
        out.append(record)
    return out


def _token_rects_for_span(line: dict, start: int, end: int, padding: float) -> list[fitz.Rect]:
    rects = []
    for key in ("spans", "tokens"):
        for token in line.get(key) or []:
            token_start, token_end = _span_bounds(token)
            if token_start is None or token_end is None or not _overlaps(start, end, token_start, token_end):
                continue
            rect = _rect_from_bbox(token.get("bbox"), padding)
            if rect is not None:
                rects.append(rect)
    return rects


def _parse_location_span(location: Any) -> tuple[int, int] | None:
    if isinstance(location, dict):
        try:
            return int(location.get("start")), int(location.get("end"))
        except Exception:
            return None
    match = re.fullmatch(r"span_(\d+)_(\d+)", str(location or "").strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _span_bounds(item: dict) -> tuple[int | None, int | None]:
    try:
        return int(item.get("char_start")), int(item.get("char_end"))
    except Exception:
        return None, None


def _overlaps(start: int, end: int, other_start: int, other_end: int) -> bool:
    return max(start, other_start) < min(end, other_end)


def _rect_from_bbox(bbox: Any, padding: float) -> fitz.Rect | None:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        rect = fitz.Rect(*[float(value) for value in bbox])
    except Exception:
        return None
    if padding:
        rect = fitz.Rect(rect.x0 - padding, rect.y0 - padding, rect.x1 + padding, rect.y1 + padding)
    return rect


def _rect_key(page_num: int, rect: fitz.Rect) -> tuple[int, int, int, int, int]:
    return (page_num, int(round(rect.x0)), int(round(rect.y0)), int(round(rect.x1)), int(round(rect.y1)))
