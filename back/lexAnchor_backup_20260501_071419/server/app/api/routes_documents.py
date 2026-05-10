from __future__ import annotations

from fastapi import APIRouter

from app.models import RedactTextRequest, RedactTextResponse
from app.services.service_factory import get_redaction_service

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("/redact-text", response_model=RedactTextResponse)
def redact_text(request: RedactTextRequest) -> RedactTextResponse:
    result = get_redaction_service().redact_text(
        request.text,
        mask=request.mask,
        detect_names=request.detect_names,
    )
    return RedactTextResponse(**result)
