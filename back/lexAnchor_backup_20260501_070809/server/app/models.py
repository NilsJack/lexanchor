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


class RedactTextRequest(BaseModel):
    text: str = Field(..., min_length=1)
    mask: str = "[REDACTED]"
    detect_names: bool = False


class RedactTextResponse(BaseModel):
    redacted_text: str
    findings: list[dict[str, Any]]
    summary: dict[str, int]
