from __future__ import annotations

from fastapi import APIRouter, Request

from app.models import LawyerUiRecommendationResponse, RuleDraftRequest, RuleDraftResponse
from app.services.access_control import scope_from_request
from app.services.service_factory import get_audit_log_store, get_rule_draft_generator

router = APIRouter(prefix="/api/v1/rule-authoring", tags=["rule-authoring"])


@router.post("/draft-from-text", response_model=RuleDraftResponse)
def draft_rules_from_text(payload: RuleDraftRequest, request: Request) -> RuleDraftResponse:
    scope = scope_from_request(request)
    result = get_rule_draft_generator().generate(
        guide_text=payload.guide_text,
        rule_scope=payload.rule_scope,
        scope_id=payload.scope_id,
        source_name=payload.source_name,
        max_rules=payload.max_rules,
    )
    get_audit_log_store().record_event(
        scope=scope,
        event_type="rule_draft.created",
        resource_type="rule_draft",
        resource_id=result["draft_id"],
        metadata={"rule_scope": payload.rule_scope, "scope_id": payload.scope_id, "rules_count": result["rules_count"]},
    )
    return RuleDraftResponse(**result)


@router.get("/lawyer-ui-recommendations", response_model=LawyerUiRecommendationResponse)
def lawyer_ui_recommendations() -> LawyerUiRecommendationResponse:
    return LawyerUiRecommendationResponse(
        role="legal_reviewer",
        principles=[
            "把合同审查当成工作台，不做营销式首页。",
            "默认展示待处理风险、义务、关系和动作，不要求律师先读长说明。",
            "规则草案必须先审核再启用，启用动作需要显示来源、范围和影响。",
            "所有下载、状态变更和规则草案操作都应有审计轨迹。",
        ],
        primary_views=[
            {
                "view": "review_workspace",
                "purpose": "单份合同审查工作台。",
                "components": ["document_viewer", "anchor_sidebar", "action_queue", "audit_timeline"],
                "server_endpoints": ["POST /api/v1/contract/scan", "GET /api/v1/jobs/{job_id}", "GET /api/v1/jobs/{job_id}/actions"],
            },
            {
                "view": "action_queue",
                "purpose": "律师推进 Action Anchor 状态。",
                "components": ["priority_filter", "status_tabs", "owner_role_filter", "bulk_export"],
                "server_endpoints": ["PATCH /api/v1/jobs/{job_id}/actions/{action_id}", "GET /api/v1/jobs/{job_id}/audit-events"],
            },
            {
                "view": "rule_authoring",
                "purpose": "把律师审查指南转成待审核规则草案。",
                "components": ["guide_input", "draft_rule_table", "keyword_editor", "negative_filter_editor", "test_examples"],
                "server_endpoints": ["POST /api/v1/rule-authoring/draft-from-text", "GET /api/v1/rulesets/{ruleset_id}"],
            },
            {
                "view": "audit_center",
                "purpose": "按 job/action/rule draft 查看审计记录。",
                "components": ["event_type_filter", "scope_badge", "resource_link", "export_button"],
                "server_endpoints": ["GET /api/v1/audit/events", "GET /api/v1/jobs/{job_id}/audit-events"],
            },
        ],
        workflow=[
            {"step": "upload_or_paste", "label": "上传或粘贴合同", "primary_endpoint": "POST /api/v1/contract/scan-text"},
            {"step": "review_anchors", "label": "查看风险、缺失、义务、关系", "primary_endpoint": "GET /api/v1/jobs/{job_id}"},
            {"step": "advance_actions", "label": "接受、推进或关闭 Action Anchor", "primary_endpoint": "PATCH /api/v1/jobs/{job_id}/actions/{action_id}"},
            {"step": "author_rules", "label": "从审查指南生成规则草案", "primary_endpoint": "POST /api/v1/rule-authoring/draft-from-text"},
            {"step": "audit", "label": "查看任务和动作审计", "primary_endpoint": "GET /api/v1/jobs/{job_id}/audit-events"},
        ],
        server_hardening=[
            {"area": "auth", "recommendation": "Replace header-only scope with signed auth tokens and membership checks.", "priority": "critical"},
            {"area": "rule_governance", "recommendation": "Persist rule drafts separately with reviewer approval, versioning, and activation workflow.", "priority": "critical"},
            {"area": "audit", "recommendation": "Make audit logs append-only and add retention/export controls for auditor roles.", "priority": "high"},
            {"area": "workflow", "recommendation": "Move actions from job result JSON into a dedicated action table with transitions and assignment.", "priority": "high"},
            {"area": "storage", "recommendation": "Move from local filesystem/SQLite to PostgreSQL plus object storage before team deployment.", "priority": "high"},
            {"area": "validation", "recommendation": "Add rule draft test cases and collision checks before enabling generated rules.", "priority": "medium"},
        ],
    )
