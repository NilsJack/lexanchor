from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models import DevSessionLoginRequest, SessionMeResponse, SessionResponse
from app.services.access_control import RequestScope, scope_from_request, session_token_from_request
from app.services.service_factory import get_audit_log_store, get_membership_store, get_session_store

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("/dev-login", response_model=SessionResponse)
def dev_login(payload: DevSessionLoginRequest) -> SessionResponse:
    user_id = payload.user_id.strip()
    organization_id = payload.organization_id.strip()
    workspace_id = payload.workspace_id.strip()
    membership = get_membership_store().get_membership(
        user_id=user_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
    )
    role_source = "membership"
    if not membership:
        membership = get_membership_store().grant_membership(
            user_id=user_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            roles=payload.roles,
            status="active",
        )
        role_source = "dev_bootstrap"
    session = get_session_store().create_session(
        user_id=user_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        roles=membership["roles"],
        ttl_hours=payload.ttl_hours,
    )
    scope = RequestScope(
        user_id=session["user_id"],
        organization_id=session["organization_id"],
        workspace_id=session["workspace_id"],
        roles=tuple(session["roles"]),
        session_id=session["session_id"],
    )
    get_audit_log_store().record_event(
        scope=scope,
        event_type="session.created",
        resource_type="session",
        resource_id=session["session_id"],
        metadata={"roles": session["roles"], "expires_at": session["expires_at"], "membership_id": membership["membership_id"], "role_source": role_source},
    )
    if role_source == "dev_bootstrap":
        get_audit_log_store().record_event(
            scope=scope,
            event_type="membership.created",
            resource_type="membership",
            resource_id=membership["membership_id"],
            metadata={"roles": membership["roles"], "source": "dev_login_bootstrap"},
        )
    return SessionResponse(**session)


@router.get("/me", response_model=SessionMeResponse)
def me(request: Request) -> SessionMeResponse:
    scope = scope_from_request(request)
    return SessionMeResponse(
        session_id=scope.session_id,
        user_id=scope.user_id,
        organization_id=scope.organization_id,
        workspace_id=scope.workspace_id,
        roles=list(scope.roles),
        authenticated=bool(scope.session_id),
    )


@router.delete("/current")
def logout(request: Request) -> dict:
    token = session_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Session token required")
    session = get_session_store().revoke_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    scope = RequestScope(
        user_id=session["user_id"],
        organization_id=session["organization_id"],
        workspace_id=session["workspace_id"],
        roles=tuple(session["roles"]),
        session_id=session["session_id"],
    )
    get_audit_log_store().record_event(
        scope=scope,
        event_type="session.revoked",
        resource_type="session",
        resource_id=session["session_id"],
    )
    return {"ok": True, "session_id": session["session_id"], "revoked": True}
