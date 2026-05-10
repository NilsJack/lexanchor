from __future__ import annotations

from fastapi import FastAPI

from app.api.routes_api_docs import router as api_docs_router
from app.api.routes_audit import router as audit_router
from app.api.routes_contract import router as contract_router
from app.api.routes_documents import router as documents_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_rules import router as rules_router
from app.config import get_settings

app = FastAPI(
    title="LexAnchor Server",
    version="0.1.0",
    description="Server-side API for legal anchor tools, document review, redaction, and legal team workflows.",
)


@app.on_event("startup")
def startup() -> None:
    get_settings().ensure_directories()


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "ok": True,
        "service": "lexanchor-server",
        "version": "0.1.0",
        "storage_dir": str(settings.storage_dir),
    }


app.include_router(contract_router)
app.include_router(documents_router)
app.include_router(jobs_router)
app.include_router(rules_router)
app.include_router(audit_router)
app.include_router(api_docs_router)
