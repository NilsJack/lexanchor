from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.models import MembershipGrantRequest, MembershipResponse
from app.services.access_control import assert_permission, scope_from_request
from app.services.service_factory import get_audit_log_store, get_membership_store

router = APIRouter(prefix="/api/v1/memberships", tags=["memberships"])


@router.post("/dev-grant", response_model=MembershipResponse)
def grant_membership(payload: MembershipGrantRequest, request: Request) -> MembershipResponse:
    scope = scope_from_request(request)
    assert_permission(scope, "membership:write")
    membership = get_membership_store().grant_membership(
        user_id=payload.user_id.strip(),
        organization_id=payload.organization_id.strip(),
        workspace_id=payload.workspace_id.strip(),
        roles=payload.roles,
        status=payload.status,
    )
    get_audit_log_store().record_event(
        scope=scope,
        event_type="membership.granted",
        resource_type="membership",
        resource_id=membership["membership_id"],
        metadata={"target_user_id": membership["user_id"], "roles": membership["roles"], "status": membership["status"]},
    )
    return MembershipResponse(**membership)


@router.get("")
def list_memberships(
    request: Request,
    organization_id: str | None = Query(None),
    workspace_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    scope = scope_from_request(request)
    assert_permission(scope, "membership:read")
    target_org = organization_id or scope.organization_id
    target_workspace = workspace_id or scope.workspace_id
    memberships = get_membership_store().list_memberships(
        organization_id=target_org,
        workspace_id=target_workspace,
        limit=limit,
    )
    return {"memberships": memberships, "count": len(memberships)}
