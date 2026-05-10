# LexAnchor Anchor Server Design

## 1. Positioning

LexAnchor Server is the backend platform for a legal working group inside a company or law team. It turns the current demo contract review POC into a multi-tenant service that can manage documents, run anchor tools, redact sensitive information, store review evidence, and expose stable APIs for agents and future frontends.

The core product claim stays unchanged:

> Anchoring is not text highlighting. It fixes a legal judgment at the point where that judgment becomes reviewable.

The platform should therefore preserve the full legal reasoning chain:

```text
Text -> Meaning -> Risk -> Obligation -> Decision -> Action
```

v0.1 deliberately starts with a narrower, reliable chain:

```text
Text Anchor + Missing Anchor + Risk Anchor + Context Anchor
```

The server architecture leaves extension points for Semantic, Escalation, Relation, Obligation, and Action anchors without forcing those capabilities into the first production slice. v0.1.1 is an engineering completion step for v0.1, not a new anchor maturity layer.

## 2. Product Scope

### 2.1 Target Users

- Enterprise legal teams and in-house counsel.
- Procurement or business legal reviewers.
- Junior associates using the platform as a first-pass safety net.
- Internal agents or workflow tools that need a stable legal review backend.

### 2.2 Server Responsibilities

The server owns professional backend capabilities:

- Organization and workspace aware document intake.
- Document storage and text extraction.
- Sensitive data redaction and redaction previews.
- Anchor rule loading and layered rule overlays.
- Anchor scanning jobs, synchronous and asynchronous.
- Structured JSON reports, Markdown reports, and future annotated PDF artifacts.
- Job tracking, auditability, and persisted review outputs.
- Minimal Action Anchor status workflow and scoped audit event retrieval.
- Rule draft generation from lawyer guidance text, with lawyer review before activation.
- Stable APIs for agents and legal tools.

The server does not own long-form chat, conversational memory, or final legal advice. Agents and frontends call the server, explain the result, and keep the human reviewer in the loop.

## 3. Anchor System Roadmap

| Version | Anchor Types | Product Goal |
| --- | --- | --- |
| v0.1 | Text, Missing, Risk, Context | Reliable red-flag first pass with explicit risk and contract interpretation coordinates. |
| v0.1.1 | No new anchor type | Complete v0.1 engineering delivery: PDF artifact, layout grounding, report downloads, E2E tests. |
| v0.2 | Semantic, Escalation | Validate ambiguous findings and promote review routing/escalation to first-class anchors. |
| v0.3 | Obligation, Relation | Extract duty structures and cross-clause dependencies. |
| v1.0 | Action | Turn review findings into workflow actions, approvals, playbooks, and negotiation tasks. |

## 4. Architecture

```text
API Layer
 - `created_by`
  RuleLoader           base / industry / organization overlays
  ContextDetector      lightweight jurisdiction/language/type detection
  FindingBuilder       normalized finding schema
  RiskMapper           severity, confidence, escalation policy
  AuditLogStore        scoped audit event persistence

Infrastructure
  SQLite               v0.1 metadata database
  Local filesystem     v0.1 document and report storage
  Future object store  S3/MinIO/OSS for 1.0 deployments
  Future queue         Redis/RQ/Celery/Temporal for scalable jobs
```

## 5. Data Model

### 5.1 Organization Model

v0.1 keeps organization and workspace as metadata fields. v1.0 should promote them to first-class database tables.

```text
Organization -> Workspace -> Matter/Project -> Document -> Job -> Findings/Artifacts
```

### 5.2 Document Model

A document record should eventually contain:

- `document_id`
- `organization_id`
- `workspace_id`
- `matter_id`
- `file_name`
- `file_type`
- `sha256`
- `storage_path`
- `extraction_status`
- `created_by`
- `created_at`

v0.1 stores uploaded files on disk and puts job metadata into SQLite.

### 5.3 Job Model

A job record contains:

- `job_id`
- `organization_id`
- `workspace_id`
- `created_by`
- `status`: queued, running, completed, failed
- `progress`
- `request_json`
- `result_json`
- `error`
- `created_at`
- `updated_at`

### 5.4 Future Workgroup Permissions

v0.1.1 keeps the current request-scope isolation only. Full workgroup permission settings are deferred to the v1.0 authorization layer.

The future model should separate object ownership from role permissions:

- Organization admins manage users, workspaces, matters, and retention policies.
- Workspace managers grant matter-level access to lawyers, business submitters, and auditors.
- Reviewers can read assigned documents, run anchor reviews, comment, and export permitted artifacts.
- Business submitters can upload and read their own submitted materials, but cannot see unrelated legal-team work.
- Auditors can read immutable access logs and review decisions, without editing findings or documents.

Every document, job, report, and artifact access should be authorized through organization, workspace, matter, role, and explicit assignment checks. Unauthorized reads should continue to return 404 for object endpoints to avoid leaking object existence.

Current development builds now include lightweight audit events scoped by `created_by`, `organization_id`, and `workspace_id`. These logs cover scan lifecycle, job/artifact reads, action reads, and action status updates. Production-grade immutable retention, auditor roles, and centralized log export remain part of the future authorization/audit layer.

### 5.5 Finding Model

All anchor results use a single normalized finding shape:

```json
{
  "finding_id": "F-0001",
  "rule_id": "contract.unlimited_liability",
  "rule_name": "Unlimited liability",
  "anchor_type": "text",
  "anchor_layer": "perception",
  "status": "confirmed",
  "severity": "critical",
  "risk": {
    "severity": "critical",
    "risk_type": "liability",
    "confidence": 0.9,
    "human_review_needed": true
  },
  "escalation": {
    "required": true,
    "reason": "critical severity or explicit rule escalation"
  },
  "evidence": {
    "matched_text": "without limitation of liability",
    "trigger": "without limitation of liability",
    "location": {"start": 120, "end": 151}
  },
  "recommendation": "Add a liability cap and exclude indirect damages."
}
```

Missing anchors must not fake a text location. They are document-level legal absence findings.

## 6. Rule Layering

Rule resolution order:

```text
base ruleset -> industry overlay -> organization overlay
```

- Base rules define general legal red flags.
- Industry overlays add domain-specific risk points.
- Organization overlays encode a legal team's playbook and risk appetite.

Later rules with the same `rule_id` override earlier rules. New `rule_id` values append new rules.

## 7. API Surface

v0.1 endpoints:

```text
GET  /health
GET  /api/v1/rulesets
GET  /api/v1/rulesets/{ruleset_id}
POST /api/v1/contract/scan-text
POST /api/v1/contract/scan
POST /api/v1/contract/scan-async
GET  /api/v1/jobs/{job_id}
GET  /api/v1/jobs/{job_id}/report.json
GET  /api/v1/jobs/{job_id}/report.md
GET  /api/v1/jobs/{job_id}/annotated.pdf
GET  /api/v1/jobs/{job_id}/actions
PATCH /api/v1/jobs/{job_id}/actions/{action_id}
GET  /api/v1/jobs/{job_id}/audit-events
GET  /api/v1/audit/events
POST /api/v1/rule-authoring/draft-from-text
GET  /api/v1/rule-authoring/lawyer-ui-recommendations
POST /api/v1/documents/redact-text
```

Future 1.0 endpoints:

```text
POST /api/v1/organizations
POST /api/v1/workspaces
POST /api/v1/matters
POST /api/v1/documents
GET  /api/v1/documents/{document_id}
POST /api/v1/anchor-runs
POST /api/v1/actions
POST /api/v1/playbooks
```

## 8. v0.1 Delivery

v0.1 implemented in this repository should provide:

- FastAPI service skeleton.
- SQLite job persistence.
- Local storage directories.
- Text and file scan APIs.
- Ruleset inspection APIs.
- Text, missing, risk, and context anchor scanning.
- Negative filter suppression.
- Lightweight context detection.
- JSON and Markdown reports.
- Redaction preview API.
- Unit tests for the rule engine.

v0.1.1 adds the PDF artifact loop: layout-aware PDF extraction, report artifact URLs, and annotated PDF rendering behind the same report/artifact contract.

The current v1.0 runtime foundation adds a minimal action loop on top of Action Anchors: scan output creates proposed actions, the creating scope can read and update action status, and audit events record the lifecycle. This is the basic operational loop, not yet a durable production workflow engine.

Rule authoring now has an automation starting point: lawyer guidance text can be converted into disabled rule drafts with keywords, severity, category, negative filters, recommendations, and review checklist. Draft generation should remain separate from rule activation so lawyers retain control over their knowledge assets.

## 9. v1.0 Target Architecture

v1.0 should become a legal operations backend:

- PostgreSQL for organizations, users, documents, runs, anchors, comments, and actions.
- Object storage for original documents, extracted text, OCR checkpoints, and rendered artifacts.
- Queue workers for OCR, LLM validation, rendering, and batch review.
- RBAC for organization admin, legal reviewer, business submitter, and auditor roles.
- Audit logs for every document access and review decision.
- Playbook engine for company-specific review policies.
- Personalized rule libraries for individual lawyers, with add/delete/edit/test/version controls.
- Rule-scope inheritance from platform baseline -> industry pack -> company playbook -> workspace/matter -> personal lawyer rules.
- Human review workflow for escalation anchors.
- Action anchors that create tasks, approval gates, negotiation suggestions, and redline requests.
- Metrics dashboards for legal risk categories and review cycle time.

## 10. Engineering Principle

The server should scale by adding capabilities around a stable anchor contract, not by turning every feature into a special case. Each future legal tool should produce compatible anchors, findings, reports, artifacts, and actions.
