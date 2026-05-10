from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ScanTextRequest(BaseModel):
    text: str = Field(..., min_length=1)
    file_name: str | None = None
    document_id: str | None = None
    ruleset: str = "rules_v0.1"
    industry_id: str | None = None
    org_id: str | None = None
    organization_id: str | None = None
    workspace_id: str | None = None
    created_by: str | None = None
    anchor_profile: str | None = None
    enabled_anchors: str | list[str] | None = None
    extraction_backend: str | None = None
    grounding_backend: str | None = None
    semantic_validation: str | None = None
    escalation_policy: str | None = None
    action_policy: str | None = None
    render_pdf: bool = False
    return_markdown: bool = True


class ScanResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    result: dict[str, Any] | None = None
    report_url: str | None = None
    markdown_report_url: str | None = None


class JobRecord(BaseModel):
    job_id: str
    status: str
    progress: int = 0
    organization_id: str | None = None
    workspace_id: str | None = None
    request: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ActionUpdateRequest(BaseModel):
    status: Literal["proposed", "accepted", "in_progress", "completed", "dismissed"]
    decision: str | None = None
    comment: str | None = None


class RuleDraftRequest(BaseModel):
    guide_text: str = Field(..., min_length=1)
    rule_scope: Literal["personal", "workspace", "company", "industry"] = "personal"
    scope_id: str = "personal"
    source_name: str | None = None
    max_rules: int = Field(12, ge=1, le=50)


class RuleDraftResponse(BaseModel):
    ok: bool
    draft_id: str
    rule_scope: str
    scope_id: str
    rules_count: int
    rules: list[dict[str, Any]]
    review_checklist: list[str]
    warnings: list[str] = Field(default_factory=list)


class LawyerUiRecommendationResponse(BaseModel):
    role: str
    principles: list[str]
    primary_views: list[dict[str, Any]]
    workflow: list[dict[str, Any]]
    server_hardening: list[dict[str, Any]]


class DevSessionLoginRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    roles: list[str] = Field(default_factory=lambda: ["legal_reviewer"])
    ttl_hours: int = Field(12, ge=1, le=168)


class MembershipGrantRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    roles: list[str] = Field(..., min_length=1)
    status: Literal["active", "disabled"] = "active"


class MembershipResponse(BaseModel):
    membership_id: str
    user_id: str
    organization_id: str
    workspace_id: str
    roles: list[str]
    status: str
    created_at: str
    updated_at: str


class SessionResponse(BaseModel):
    session_id: str
    session_token: str
    token_type: str = "Bearer"
    user_id: str
    organization_id: str
    workspace_id: str
    roles: list[str]
    expires_at: str


class SessionMeResponse(BaseModel):
    session_id: str | None = None
    user_id: str
    organization_id: str
    workspace_id: str
    roles: list[str] = Field(default_factory=list)
    authenticated: bool


class RedactTextRequest(BaseModel):
    text: str = Field(..., min_length=1)
    mask: str = "[REDACTED]"
    detect_names: bool = False


class RedactTextResponse(BaseModel):
    redacted_text: str
    findings: list[dict[str, Any]]
    summary: dict[str, int]
