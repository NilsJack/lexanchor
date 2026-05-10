from __future__ import annotations

from fastapi import APIRouter, Request

from app.models import RedactTextRequest, RedactTextResponse
from app.services.access_control import assert_permission, scope_from_request
from app.services.service_factory import get_redaction_service

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("/redact-text", response_model=RedactTextResponse)
def redact_text(payload: RedactTextRequest, request: Request) -> RedactTextResponse:
    assert_permission(scope_from_request(request), "document:redact")
    result = get_redaction_service().redact_text(
        payload.text,
        mask=payload.mask,
        detect_names=payload.detect_names,
    )
    return RedactTextResponse(**result)
