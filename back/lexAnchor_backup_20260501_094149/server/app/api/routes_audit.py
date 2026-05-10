from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.services.access_control import assert_permission, scope_from_request
from app.services.service_factory import get_audit_log_store

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/events")
def list_audit_events(
    request: Request,
    resource_type: str | None = Query(None),
    resource_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    scope = scope_from_request(request)
    assert_permission(scope, "audit:read")
    events = get_audit_log_store().list_events(
        scope=scope,
        resource_type=resource_type,
        resource_id=resource_id,
        limit=limit,
    )
    return {"events": events, "count": len(events)}
