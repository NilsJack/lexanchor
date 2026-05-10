from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request

from app.config import get_settings


@dataclass(frozen=True)
class RequestScope:
    user_id: str
    organization_id: str
    workspace_id: str


def scope_from_request(
    request: Request,
    *,
    organization_id: str | None = None,
    workspace_id: str | None = None,
    user_id: str | None = None,
) -> RequestScope:
    settings = get_settings()
    return RequestScope(
        user_id=_clean(request.headers.get("x-user-id") or user_id or settings.default_user_id),
        organization_id=_clean(request.headers.get("x-organization-id") or organization_id or settings.default_organization_id),
        workspace_id=_clean(request.headers.get("x-workspace-id") or workspace_id or settings.default_workspace_id),
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


def _clean(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Invalid request scope")
    return text
