# LexAnchor Server v1.0 Roadmap

## 1. v1.0 Goal

v1.0 should evolve LexAnchor from a contract-review API into a legal work platform for company legal teams. The platform should manage documents, legal matters, review runs, anchor evidence, redaction artifacts, playbooks, escalations, and legal tool execution.

The core design principle is that every legal tool should produce reviewable anchors, not isolated text output.

```text
Legal Tool -> Anchors -> Findings -> Review Decisions -> Actions -> Audit Trail
```

## 2. Product Modules

### 2.1 Team Workspace

- Organizations.
- Workspaces.
- Matters or projects.
- Role-based access control.
- Review assignment.
- Internal comments and decisions.
- Audit log for every document and finding access.

Initial roles:

- Organization Admin.
- Legal Reviewer.
- Business Submitter.
- External Counsel.
- Auditor.

### 2.2 Document Service

- Original document upload.
- Text extraction and OCR jobs.
- Document versioning.
- Extracted text and layout index storage.
- Artifact storage for reports, redactions, annotated PDFs, and exported packets.
- Document lineage across versions and redlines.

### 2.3 Redaction Service

- PII and sensitive commercial term detection.
- Redaction preview.
- Redacted document artifact generation.
- Redaction policies per organization.
- Redaction audit events.

### 2.4 Anchor Services

Anchor services should be a family, not a single endpoint:

- Contract Review Anchor Service.
- Compliance Anchor Service.
- Missing Clause Anchor Service.
- Risk Anchor Service.
- Obligation Anchor Service.
- Relation Anchor Service.
- Action Anchor Service.

All services should emit compatible finding records.

### 2.5 Legal Tool Platform

The legal tool platform should register tools by capability:

- Contract scan.
- NDA review.
- Privacy review.
- Terms review.
- Clause comparison.
- Missing clause detection.
- Negotiation playbook generation.
- Legal compliance checklist.
- PDF report generation.

Each tool definition should include:

- Input schema.
- Output schema.
- Anchor types produced.
- Required document capabilities.
- Whether it may use LLM validation.
- Whether human review is mandatory.

## 3. Backend Architecture

```text
API Gateway / FastAPI
  Auth, RBAC, OpenAPI, webhooks

Application Services
  OrganizationService
  WorkspaceService
  MatterService
  DocumentService
  RedactionService
  AnchorRunService
  LegalToolRegistry
  ReviewWorkflowService
  ReportService
  AuditLogService

Worker Layer
  OCR worker
  Extraction worker
  Anchor scan worker
  LLM validation worker
  PDF rendering worker
  Batch export worker

Data Layer
  PostgreSQL
  Object storage
  Redis queue/cache
  Vector store for retrieval and precedent search
```

## 4. Database Direction

PostgreSQL tables:

- `organizations`
- `users`
- `memberships`
- `workspaces`
- `matters`
- `documents`
- `document_versions`
- `document_artifacts`
- `anchor_runs`
- `findings`
- `context_anchors`
- `review_decisions`
- `actions`
- `comments`
- `playbooks`
- `rulesets`
- `audit_events`

v0.1 SQLite job records should map cleanly to `anchor_runs` in v1.0.

## 5. Anchor Maturity Plan

### v0.1 Implemented Now

- Text Anchor.
- Missing Anchor.
- Risk Anchor.
- Lightweight Context Anchor.
- Semantic Candidate as report-only/debug evidence, not a confirmed Semantic Anchor.

### v0.1.1 Engineering Completion

- PDF annotated artifact pipeline.
- Layout-backed evidence grounding for PDF output.
- Stable artifact URLs for JSON, Markdown, and annotated PDF.
- Docling extraction hardening.
- LangExtract grounding hardening.
- End-to-end tests for text, TXT, DOCX, and PDF scans.

### v0.2

- LLM semantic validation.
- Confirmed Semantic Anchor output.
- Escalation Anchor policy and review routing.
- Escalation metadata for human review queues.
- Async queue instead of in-process background tasks.

### v0.3

- Obligation extraction.
- Relation graph between clauses.
- Clause-level dependency checks.
- Playbook-based risk appetite.

### v1.0

- Action Anchor.
- Review workflow.
- Team collaboration.
- Audit logs.
- Legal tool registry.
- Organization-specific rules and playbooks.
- Personalized rule libraries for individual lawyers, with explicit promotion paths into team or company rules.
- Production deployment package.

## 6. Production Non-Functional Requirements

- Tenant isolation by organization.
- Access control on every document and artifact.
- Immutable audit logs for sensitive operations.
- Worker retries and idempotent job processing.
- Large file handling and resumable uploads.
- Observability for OCR, extraction, LLM validation, and rendering.
- Configurable retention policy.
- Exportable evidence packet for human legal review.

## 7. v1.0 API Families

```text
/api/v1/organizations
/api/v1/workspaces
/api/v1/matters
/api/v1/documents
/api/v1/redactions
/api/v1/anchor-runs
/api/v1/findings
/api/v1/review-decisions
/api/v1/actions
/api/v1/playbooks
/api/v1/tools
/api/v1/audit-events
```

## 8. Migration From v0.1

- Keep v0.1 `scan-text` and `scan` endpoints as compatibility wrappers.
- Move SQLite job store to PostgreSQL `anchor_runs`.
- Move local storage to object storage.
- Move in-process async to queue workers.
- Keep finding JSON schema backward compatible.
- Promote `organization_id` and `workspace_id` from metadata to required authorization scope.

## 9. Definition of Done for v1.0

v1.0 is ready when a company legal team can:

1. Create a workspace and matter.
2. Upload documents safely.
3. Run redaction and anchor review tools.
4. Review findings with evidence and recommendations.
5. Assign escalations and record decisions.
6. Export reports and annotated artifacts.
7. Audit who accessed or changed each legal judgment.
