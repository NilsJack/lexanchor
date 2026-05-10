from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from app.models import ActionUpdateRequest
from app.services.access_control import RequestScope, assert_job_access, assert_permission, scope_from_request
from app.services.service_factory import get_audit_log_store, get_job_store

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job(job_id: str, request: Request) -> dict:
    job, scope = _scoped_job_with_scope(job_id, request, permission="job:read")
    _record_audit(scope, "job.read", "job", job_id, metadata={"status": job.get("status")})
    return job


@router.get("/{job_id}/report.json")
def get_json_report(job_id: str, request: Request):
    job, scope = _scoped_job_with_scope(job_id, request, permission="artifact:read")
    _record_audit(scope, "artifact.read", "report.json", job_id)
    result = job.get("result") or {}
    path = ((result.get("artifacts") or {}).get("json_report_path"))
    if path and Path(path).exists():
        return FileResponse(path, media_type="application/json", filename="report.json")
    return JSONResponse(result)


@router.get("/{job_id}/report.md")
def get_markdown_report(job_id: str, request: Request):
    job, scope = _scoped_job_with_scope(job_id, request, permission="artifact:read")
    _record_audit(scope, "artifact.read", "report.md", job_id)
    result = job.get("result") or {}
    path = ((result.get("artifacts") or {}).get("markdown_report_path"))
    if path and Path(path).exists():
        return FileResponse(path, media_type="text/markdown", filename="report.md")
    return PlainTextResponse("Report is not ready.", status_code=404)


@router.get("/{job_id}/annotated.pdf")
def get_annotated_pdf(job_id: str, request: Request):
    job, scope = _scoped_job_with_scope(job_id, request, permission="artifact:read")
    _record_audit(scope, "artifact.read", "annotated.pdf", job_id)
    result = job.get("result") or {}
    path = ((result.get("artifacts") or {}).get("annotated_pdf_path"))
    if path and Path(path).exists():
        return FileResponse(path, media_type="application/pdf", filename="annotated.pdf")
    return PlainTextResponse("Annotated PDF is not ready.", status_code=404)


@router.get("/{job_id}/actions")
def list_actions(job_id: str, request: Request) -> dict:
    job, scope = _scoped_job_with_scope(job_id, request, permission="action:read")
    result = job.get("result") or {}
    actions = list(result.get("action_anchors") or [])
    _record_audit(scope, "actions.read", "job", job_id, metadata={"action_count": len(actions)})
    return {
        "job_id": job_id,
        "action_policy": result.get("action_policy") or {},
        "action_queue": result.get("action_queue") or {"enabled": False, "item_count": 0, "items": []},
        "action_anchors": actions,
    }


@router.patch("/{job_id}/actions/{action_id}")
def update_action(job_id: str, action_id: str, payload: ActionUpdateRequest, request: Request) -> dict:
    job, scope = _scoped_job_with_scope(job_id, request, permission="action:update")
    result = dict(job.get("result") or {})
    actions = list(result.get("action_anchors") or [])
    action = next((item for item in actions if item.get("action_id") == action_id), None)
    if not action:
        _record_audit(scope, "action.update", "action", action_id, outcome="not_found", metadata={"job_id": job_id})
        raise HTTPException(status_code=404, detail="Action not found")

    now = datetime.now(timezone.utc).isoformat()
    action["status"] = payload.status
    action["decision"] = payload.decision
    action["comment"] = payload.comment
    action["updated_by"] = scope.user_id
    action["updated_at"] = now
    _update_queue_item(result, action_id, payload.status)
    result["action_anchors"] = actions
    get_job_store().update_job(job_id, result=result)
    _record_audit(
        scope,
        "action.update",
        "action",
        action_id,
        metadata={"job_id": job_id, "status": payload.status, "decision": payload.decision},
    )
    return {"job_id": job_id, "action": action, "action_queue": result.get("action_queue") or {}}


@router.get("/{job_id}/audit-events")
def list_job_audit_events(job_id: str, request: Request, limit: int = 100) -> dict:
    _job, scope = _scoped_job_with_scope(job_id, request, permission="audit:read")
    events = get_audit_log_store().list_events(
        scope=scope,
        resource_type="job",
        resource_id=job_id,
        limit=limit,
    )
    return {"job_id": job_id, "events": events, "count": len(events)}


def _scoped_job(job_id: str, request: Request) -> dict:
    job, _scope = _scoped_job_with_scope(job_id, request, permission="job:read")
    return job


def _scoped_job_with_scope(job_id: str, request: Request, *, permission: str | None = None) -> tuple[dict, RequestScope]:
    scope = scope_from_request(request)
    if permission:
        assert_permission(scope, permission)
    return assert_job_access(get_job_store().get_job(job_id), scope), scope


def _record_audit(scope: RequestScope, event_type: str, resource_type: str, resource_id: str, *, outcome: str = "success", metadata: dict | None = None) -> None:
    get_audit_log_store().record_event(
        scope=scope,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        metadata=metadata or {},
    )


def _update_queue_item(result: dict, action_id: str, status: str) -> None:
    queue = result.get("action_queue") if isinstance(result.get("action_queue"), dict) else {}
    for item in queue.get("items") or []:
        if item.get("action_id") == action_id:
            item["status"] = status
