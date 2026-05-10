from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request

from app.config import get_settings


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "org_admin": {"*"},
    "development_header_scope": {"*"},
    "legal_reviewer": {
        "contract:scan",
        "document:redact",
        "job:read",
        "artifact:read",
        "action:read",
        "action:update",
        "audit:read",
        "rule:read",
        "session:self",
    },
    "rule_author": {
        "rule:read",
        "rule_draft:create",
        "audit:read",
        "session:self",
    },
    "auditor": {
        "job:read",
        "artifact:read",
        "action:read",
        "audit:read",
        "rule:read",
        "session:self",
    },
    "workspace_manager": {
        "contract:scan",
        "document:redact",
        "job:read",
        "artifact:read",
        "action:read",
        "action:update",
        "audit:read",
        "rule:read",
        "rule_draft:create",
        "membership:read",
        "membership:write",
        "session:self",
    },
    "business_submitter": {
        "contract:scan",
        "document:redact",
        "job:read",
        "artifact:read",
        "session:self",
    },
}


@dataclass(frozen=True)
class RequestScope:
    user_id: str
    organization_id: str
    workspace_id: str
    roles: tuple[str, ...] = ()
    session_id: str | None = None


def scope_from_request(
    request: Request,
    *,
    organization_id: str | None = None,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> RequestScope:
    settings = get_settings()
    token = session_token_from_request(request)
    if token:
        session = _session_store().get_session(token)
        if not session:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        return RequestScope(
            user_id=_clean(session.get("user_id")),
            organization_id=_clean(session.get("organization_id")),
            workspace_id=_clean(session.get("workspace_id")),
            roles=tuple(session.get("roles") or ()),
            session_id=session.get("session_id"),
        )
    return RequestScope(
        user_id=_clean(request.headers.get("x-user-id") or user_id or settings.default_user_id),
        organization_id=_clean(request.headers.get("x-organization-id") or organization_id or settings.default_organization_id),
        workspace_id=_clean(request.headers.get("x-workspace-id") or workspace_id or settings.default_workspace_id),
        roles=("development_header_scope",),
    )


def attach_scope(payload: dict, scope: RequestScope) -> dict:
    out = dict(payload)
    out["created_by"] = scope.user_id
    out["organization_id"] = scope.organization_id
    out["workspace_id"] = scope.workspace_id
    return out


def assert_job_access(job: dict | None, scope: RequestScope) -> dict:
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    request_payload = job.get("request") or {}
    same_org = str(job.get("organization_id") or request_payload.get("organization_id") or "") == scope.organization_id
    same_workspace = str(job.get("workspace_id") or request_payload.get("workspace_id") or "") == scope.workspace_id
    same_user = str(job.get("created_by") or request_payload.get("created_by") or "") == scope.user_id
    if not (same_org and same_workspace and same_user):
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def has_permission(scope: RequestScope, permission: str) -> bool:
    for role in scope.roles:
        permissions = ROLE_PERMISSIONS.get(str(role), set())
        if "*" in permissions or permission in permissions:
            return True
    return False


def assert_permission(scope: RequestScope, permission: str) -> None:
    if not has_permission(scope, permission):
        raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")


def _clean(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Invalid request scope")
    return text


def session_token_from_request(request: Request) -> str | None:
    authorization = str(request.headers.get("authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    token = str(request.headers.get("x-lexanchor-session") or request.headers.get("x-session-token") or "").strip()
    return token or None


def _session_store():
    from app.services.service_factory import get_session_store

    return get_session_store()
