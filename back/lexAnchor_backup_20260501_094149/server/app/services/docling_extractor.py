from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from typing import Any


class DoclingExtractor:
    supported_suffixes = {".pdf", ".docx", ".pptx", ".html", ".htm", ".md", ".txt"}

    def __init__(self) -> None:
        self._converter: Any | None = None

    def available(self) -> bool:
        try:
            return importlib.util.find_spec("docling.document_converter") is not None
        except ModuleNotFoundError:
            return False

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.supported_suffixes

    def extract(self, path: Path) -> tuple[str, dict[str, Any]]:
        if not self.supports(path):
            raise ValueError(f"Docling does not support this file type in server integration: {path.suffix}")
        converter = self._get_converter()
        result = converter.convert(str(path))
        document = getattr(result, "document", None)
        if document is None:
            raise RuntimeError("Docling conversion returned no document")

        text = self._export_document_text(document)
        metadata = {
            "source_format": path.suffix.lower().lstrip(".") or "unknown",
            "extraction_backend": "docling",
            "docling_available": True,
        }
        page_count = self._page_count(document)
        if page_count is not None:
            metadata["total_pages"] = page_count
        return text, metadata

    def _get_converter(self) -> Any:
        if self._converter is None:
            module = importlib.import_module("docling.document_converter")
            converter_type = getattr(module, "DocumentConverter")
            self._converter = converter_type()
        return self._converter

    @staticmethod
    def _export_document_text(document: Any) -> str:
        for method_name in ("export_to_markdown", "export_to_text"):
            method = getattr(document, method_name, None)
            if callable(method):
                text = str(method() or "").strip()
                if text:
                    return text
        return str(document).strip()

    @staticmethod
    def _page_count(document: Any) -> int | None:
        pages = getattr(document, "pages", None)
        if pages is None:
            return None
        try:
            return len(pages)
        except TypeError:
            return None
