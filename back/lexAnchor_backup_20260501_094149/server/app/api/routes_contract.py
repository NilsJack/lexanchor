from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile

from app.config import get_settings
from app.models import ScanResponse, ScanTextRequest
from app.services.access_control import RequestScope, assert_permission, attach_scope, scope_from_request
from app.services.anchor_capabilities import anchor_enabled
from app.services.service_factory import (
    get_action_anchor_service,
    get_anchor_engine,
    get_document_service,
    get_escalation_policy_service,
    get_grounding_service,
    get_job_store,
    get_pdf_renderer,
    get_report_service,
    get_semantic_validator,
    get_audit_log_store,
)

router = APIRouter(prefix="/api/v1/contract", tags=["contract"])


@router.post("/scan-text", response_model=ScanResponse)
def scan_text(payload: ScanTextRequest, http_request: Request) -> ScanResponse:
    scope = scope_from_request(
        http_request,
        organization_id=payload.organization_id,
        workspace_id=payload.workspace_id,
        user_id=payload.created_by,
    )
    assert_permission(scope, "contract:scan")
    job_store = get_job_store()
    request_payload = attach_scope(_model_to_dict(payload), scope)
    job_id = job_store.create_job(
        organization_id=scope.organization_id,
        workspace_id=scope.workspace_id,
        created_by=scope.user_id,
        request=request_payload,
        status="running",
    )
    _record_scan_audit(scope, "scan_text.created", job_id, metadata={"ruleset": request_payload.get("ruleset")})
    result = _run_text_scan(job_id, payload.text, request_payload)
    _record_scan_audit(scope, "scan_text.completed", job_id, metadata={"version": result.get("version")})
    return ScanResponse(
        job_id=job_id,
        status="completed",
        result=result,
        report_url=result.get("artifacts", {}).get("json_report_url"),
        markdown_report_url=result.get("artifacts", {}).get("markdown_report_url"),
    )


@router.post("/scan", response_model=ScanResponse)
async def scan_file(
    http_request: Request,
    file: UploadFile = File(...),
    ruleset: str = Form("rules_v0.1"),
    industry_id: str | None = Form(None),
    org_id: str | None = Form(None),
    organization_id: str | None = Form(None),
    workspace_id: str | None = Form(None),
    render_pdf: bool = Form(False),
    return_markdown: bool = Form(True),
    anchor_profile: str | None = Form(None),
    enabled_anchors: str | None = Form(None),
    extraction_backend: str | None = Form(None),
    grounding_backend: str | None = Form(None),
    semantic_validation: str | None = Form(None),
    escalation_policy: str | None = Form(None),
    action_policy: str | None = Form(None),
) -> ScanResponse:
    settings = get_settings()
    scope = scope_from_request(http_request, organization_id=organization_id, workspace_id=workspace_id)
    assert_permission(scope, "contract:scan")
    request_payload = {
        "ruleset": ruleset,
        "industry_id": industry_id,
        "org_id": org_id,
        "organization_id": scope.organization_id,
        "workspace_id": scope.workspace_id,
        "created_by": scope.user_id,
        "anchor_profile": anchor_profile,
        "enabled_anchors": enabled_anchors,
        "render_pdf": render_pdf,
        "return_markdown": return_markdown,
        "extraction_backend": extraction_backend or settings.default_extraction_backend,
        "grounding_backend": grounding_backend or settings.default_grounding_backend,
        "semantic_validation": semantic_validation,
        "escalation_policy": escalation_policy,
        "action_policy": action_policy,
    }
    job_store = get_job_store()
    job_id = job_store.create_job(
        organization_id=scope.organization_id,
        workspace_id=scope.workspace_id,
        created_by=scope.user_id,
        request=request_payload,
        status="running",
    )
    _record_scan_audit(scope, "scan_file.created", job_id, metadata={"ruleset": request_payload.get("ruleset")})
    upload_meta = await get_document_service().save_upload(file, job_id)
    result = _run_file_scan(job_id, upload_meta, request_payload)
    _record_scan_audit(scope, "scan_file.completed", job_id, metadata={"version": result.get("version"), "file_name": upload_meta.get("file_name")})
    return ScanResponse(
        job_id=job_id,
        status="completed",
        result=result,
        report_url=result.get("artifacts", {}).get("json_report_url"),
        markdown_report_url=result.get("artifacts", {}).get("markdown_report_url"),
    )


@router.post("/scan-async", response_model=ScanResponse)
async def scan_file_async(
    background_tasks: BackgroundTasks,
    http_request: Request,
    file: UploadFile = File(...),
    ruleset: str = Form("rules_v0.1"),
    industry_id: str | None = Form(None),
    org_id: str | None = Form(None),
    organization_id: str | None = Form(None),
    workspace_id: str | None = Form(None),
    render_pdf: bool = Form(False),
    return_markdown: bool = Form(True),
    anchor_profile: str | None = Form(None),
    enabled_anchors: str | None = Form(None),
    extraction_backend: str | None = Form(None),
    grounding_backend: str | None = Form(None),
    semantic_validation: str | None = Form(None),
    escalation_policy: str | None = Form(None),
    action_policy: str | None = Form(None),
) -> ScanResponse:
    settings = get_settings()
    scope = scope_from_request(http_request, organization_id=organization_id, workspace_id=workspace_id)
    assert_permission(scope, "contract:scan")
    request_payload = {
        "ruleset": ruleset,
        "industry_id": industry_id,
        "org_id": org_id,
        "organization_id": scope.organization_id,
        "workspace_id": scope.workspace_id,
        "created_by": scope.user_id,
        "anchor_profile": anchor_profile,
        "enabled_anchors": enabled_anchors,
        "render_pdf": render_pdf,
        "return_markdown": return_markdown,
        "extraction_backend": extraction_backend or settings.default_extraction_backend,
        "grounding_backend": grounding_backend or settings.default_grounding_backend,
        "semantic_validation": semantic_validation,
        "escalation_policy": escalation_policy,
        "action_policy": action_policy,
    }
    job_store = get_job_store()
    job_id = job_store.create_job(
        organization_id=scope.organization_id,
        workspace_id=scope.workspace_id,
        created_by=scope.user_id,
        request=request_payload,
        status="queued",
    )
    _record_scan_audit(scope, "scan_file_queued.created", job_id, metadata={"ruleset": request_payload.get("ruleset")})
    upload_meta = await get_document_service().save_upload(file, job_id)
    background_tasks.add_task(_run_file_scan, job_id, upload_meta, request_payload)
    return ScanResponse(job_id=job_id, status="queued")


def _run_file_scan(job_id: str, upload_meta: dict[str, Any], request_payload: dict[str, Any]) -> dict[str, Any]:
    job_store = get_job_store()
    try:
        job_store.update_job(job_id, status="running", progress=15)
        text, extraction_meta = get_document_service().extract_text(
            upload_meta["storage_path"],
            backend=request_payload.get("extraction_backend") or get_settings().default_extraction_backend,
        )
        scan_payload = dict(request_payload)
        scan_payload["file_name"] = upload_meta.get("file_name")
        scan_payload["file_type"] = upload_meta.get("file_type")
        scan_payload["sha256"] = upload_meta.get("sha256")
        document_info = {
            "file_name": upload_meta.get("file_name"),
            "file_type": upload_meta.get("file_type"),
            "sha256": upload_meta.get("sha256"),
            "size_bytes": upload_meta.get("size_bytes"),
            **{key: value for key, value in extraction_meta.items() if key != "layout_map"},
        }
        result = _run_text_scan(job_id, text, scan_payload, document_info=document_info, update_running=False)
        result = _maybe_render_pdf_artifact(job_id, upload_meta, extraction_meta, result)
        if result.get("artifacts", {}).get("annotated_pdf_path"):
            persisted = get_report_service().persist_reports(job_id, result)
            result["artifacts"].update(persisted)
            job_store.update_job(job_id, status="completed", progress=100, result=result)
        return result
    except Exception as exc:
        job_store.update_job(job_id, status="failed", progress=100, error=str(exc))
        _record_payload_audit(request_payload, "scan.failed", job_id, outcome="failed", metadata={"error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _run_text_scan(
    job_id: str,
    text: str,
    request_payload: dict[str, Any],
    *,
    document_info: dict[str, Any] | None = None,
    update_running: bool = True,
) -> dict[str, Any]:
    job_store = get_job_store()
    if update_running:
        job_store.update_job(job_id, status="running", progress=20)
    engine = get_anchor_engine()
    result = engine.scan_text(
        text,
        ruleset=request_payload.get("ruleset") or "rules_v0.1",
        industry_id=request_payload.get("industry_id"),
        org_id=request_payload.get("org_id"),
        document_info=document_info or {
            "file_name": request_payload.get("file_name") or "inline_text.txt",
            "file_type": "text",
        },
        anchor_profile=request_payload.get("anchor_profile"),
        enabled_anchors=request_payload.get("enabled_anchors"),
    )
    result = _ground_scan_result(text, result, request_payload)
    result = _apply_v0_2_layers(result, request_payload)
    artifacts = {
        "json_report_url": f"/api/v1/jobs/{job_id}/report.json",
        "markdown_report_url": f"/api/v1/jobs/{job_id}/report.md",
    }
    result["artifacts"].update(artifacts)
    persisted = get_report_service().persist_reports(job_id, result)
    result["artifacts"].update(persisted)
    job_store.update_job(job_id, status="completed", progress=100, result=result)
    _record_payload_audit(request_payload, "scan.completed", job_id, metadata={"version": result.get("version")})
    return result


def _ground_scan_result(text: str, result: dict[str, Any], request_payload: dict[str, Any]) -> dict[str, Any]:
    backend = str(request_payload.get("grounding_backend") or get_settings().default_grounding_backend or "auto").strip().lower()
    if backend in {"0", "false", "off", "disabled", "none"}:
        result["grounding"] = {"enabled": False, "reason": "disabled_by_request"}
        return result
    allow_network = True if backend in {"langextract", "network"} else None
    return get_grounding_service().ground_result(text, result, allow_network=allow_network)


def _apply_v0_2_layers(result: dict[str, Any], request_payload: dict[str, Any]) -> dict[str, Any]:
    capabilities = result.get("anchor_capabilities") if isinstance(result.get("anchor_capabilities"), dict) else {}
    default_semantic_mode = "validate" if anchor_enabled(capabilities, "semantic") else "candidate"
    semantic_mode = str(request_payload.get("semantic_validation") or default_semantic_mode).strip().lower()
    escalation_policy = str(request_payload.get("escalation_policy") or ("default" if anchor_enabled(capabilities, "escalation") else "disabled")).strip().lower()
    if not anchor_enabled(capabilities, "semantic"):
        semantic_mode = "candidate"
    if not anchor_enabled(capabilities, "escalation"):
        escalation_policy = "disabled"
    result = get_semantic_validator().validate_result(result, mode=semantic_mode)
    result = get_escalation_policy_service().apply(result, policy=escalation_policy)
    action_policy = str(request_payload.get("action_policy") or ("default" if anchor_enabled(capabilities, "action") else "disabled")).strip().lower()
    if not anchor_enabled(capabilities, "action"):
        action_policy = "disabled"
    result = get_action_anchor_service().apply(result, policy=action_policy)
    return result


def _maybe_render_pdf_artifact(
    job_id: str,
    upload_meta: dict[str, Any],
    extraction_meta: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    if str(upload_meta.get("file_type") or "").lower() != "pdf":
        return result
    layout_map = extraction_meta.get("layout_map")
    if not isinstance(layout_map, dict):
        result.setdefault("artifacts", {})["annotated_pdf_error"] = "layout_map_unavailable"
        return result
    output_path = get_settings().artifacts_dir / job_id / "annotated.pdf"
    render_result = get_pdf_renderer().render_annotated_pdf(
        upload_meta["storage_path"],
        result,
        layout_map,
        str(output_path),
    )
    if render_result.get("ok"):
        result.setdefault("artifacts", {}).update(
            {
                "annotated_pdf_path": str(output_path),
                "annotated_pdf_url": f"/api/v1/jobs/{job_id}/annotated.pdf",
            }
        )
    else:
        result.setdefault("artifacts", {})["annotated_pdf_error"] = str(render_result.get("error") or "unknown_error")
    return result


def _model_to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _record_scan_audit(scope: RequestScope, event_type: str, job_id: str, *, outcome: str = "success", metadata: dict[str, Any] | None = None) -> None:
    get_audit_log_store().record_event(
        scope=scope,
        event_type=event_type,
        resource_type="job",
        resource_id=job_id,
        outcome=outcome,
        metadata=metadata or {},
    )


def _record_payload_audit(request_payload: dict[str, Any], event_type: str, job_id: str, *, outcome: str = "success", metadata: dict[str, Any] | None = None) -> None:
    get_audit_log_store().record_event(
        scope=RequestScope(
            user_id=str(request_payload.get("created_by") or get_settings().default_user_id),
            organization_id=str(request_payload.get("organization_id") or get_settings().default_organization_id),
            workspace_id=str(request_payload.get("workspace_id") or get_settings().default_workspace_id),
        ),
        event_type=event_type,
        resource_type="job",
        resource_id=job_id,
        outcome=outcome,
        metadata=metadata or {},
    )
