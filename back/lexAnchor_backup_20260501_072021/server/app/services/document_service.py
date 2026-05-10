from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.services.docling_extractor import DoclingExtractor
from app.services.layout_index import build_pdf_layout_map


class DocumentService:
    def __init__(self, uploads_dir: Path) -> None:
        self.uploads_dir = uploads_dir
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.docling = DoclingExtractor()

    async def save_upload(self, upload: UploadFile, job_id: str) -> dict[str, Any]:
        original_name = upload.filename or "uploaded_document"
        safe_name = self._safe_name(original_name)
        job_dir = self.uploads_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        output_path = job_dir / safe_name
        content = await upload.read()
        output_path.write_bytes(content)
        return {
            "file_name": original_name,
            "safe_file_name": safe_name,
            "storage_path": str(output_path),
            "file_type": output_path.suffix.lower().lstrip(".") or "unknown",
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }

    def extract_text(self, storage_path: str, *, backend: str = "auto") -> tuple[str, dict[str, Any]]:
        path = Path(storage_path)
        suffix = path.suffix.lower()
        resolved_backend = str(backend or "auto").strip().lower()

        if resolved_backend in {"auto", "docling"} and self.docling.supports(path):
            if self.docling.available():
                try:
                    return self.docling.extract(path)
                except Exception:
                    if resolved_backend == "docling":
                        raise
            elif resolved_backend == "docling":
                raise RuntimeError("Docling extraction requested but docling is not installed")

        if suffix in {".txt", ".md", ".markdown"}:
            return path.read_text(encoding="utf-8"), {"source_format": suffix.lstrip(".") or "text", "extraction_backend": "native"}
        if suffix == ".pdf":
            return self._extract_pdf(path)
        if suffix == ".docx":
            return self._extract_docx(path)
        raise ValueError(f"Unsupported file type for v0.1 extraction: {suffix or 'unknown'}")

    @staticmethod
    def _safe_name(name: str) -> str:
        cleaned = "".join(char if char.isalnum() or char in {".", "-", "_"} else "_" for char in name)
        return cleaned[:180] or "uploaded_document"

    @staticmethod
    def _extract_pdf(path: Path) -> tuple[str, dict[str, Any]]:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PDF extraction requires optional dependency pymupdf") from exc

        text_parts = []
        with fitz.open(path) as document:
            for page in document:
                text_parts.append(page.get_text())
            page_count = len(document)
        text = "\n".join(text_parts)
        layout_map = build_pdf_layout_map(str(path), extracted_text=text)
        return text, {
            "source_format": "pdf",
            "total_pages": page_count,
            "extraction_backend": "native_pymupdf",
            "layout_map": layout_map,
        }

    @staticmethod
    def _extract_docx(path: Path) -> tuple[str, dict[str, Any]]:
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("DOCX extraction requires optional dependency python-docx") from exc

        document = Document(path)
        paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        return "\n".join(paragraphs), {"source_format": "docx", "extraction_backend": "native_python_docx"}
