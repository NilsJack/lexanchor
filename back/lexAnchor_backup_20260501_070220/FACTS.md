# LexAnchor Facts

Last updated: 2026-05-01

This file records the current development state so future work can continue without rediscovering the project shape.

## Project Location

- Workspace root: `/Users/lq/projects/laws/lexAnchor`
- Server package: `server/`
- Demo POC reference: `demo/`
- Current server entrypoint: `server/app/main.py`
- Current active Python version: `server/.python-version` = `3.11`

## Environment

Use `uv` for Python environment management.

```bash
cd /Users/lq/projects/laws/lexAnchor/server
HTTP_PROXY=http://127.0.0.1:51809 HTTPS_PROXY=http://127.0.0.1:51809 UV_HTTP_TIMEOUT=120 uv sync
```

Run tests with the pinned Python version:

```bash
cd /Users/lq/projects/laws/lexAnchor/server
PYTHONDONTWRITEBYTECODE=1 HTTP_PROXY=http://127.0.0.1:51809 HTTPS_PROXY=http://127.0.0.1:51809 UV_HTTP_TIMEOUT=120 uv run --python 3.11 python -m unittest
```

Do not rely on plain `uv run python -m unittest`; that has failed in this environment because the default Python selection may differ.

## Current Server Capabilities

- FastAPI HTTP server.
- Hosted Swagger/OpenAPI docs.
- Hosted LexAnchor API docs at `/api-docs` and `/api/v1/docs/api.md`.
- Text scan endpoint.
- File scan endpoint.
- Async scan endpoint using FastAPI background tasks.
- Ruleset list and inspect endpoints.
- JSON and Markdown report artifacts.
- Annotated PDF artifact generation for PDF scans when native PDF layout metadata is available.
- Text redaction preview endpoint.
- SQLite job store.
- Local filesystem upload and artifact storage.
- Lightweight lawyer/team object isolation using request-scope headers.
- Optional Docling extraction path with native fallback.
- Optional LangExtract grounding path with local exact-string fallback.

## Access Isolation

Current development isolation uses request headers, not full authentication/RBAC:

```text
X-User-Id
X-Organization-Id
X-Workspace-Id
```

Each job is bound to `created_by`, `organization_id`, and `workspace_id`. Job metadata, artifacts, actions, and audit reads return `404` or empty scoped results when accessed from a different scope. This avoids leaking object existence through job ids.

The current runtime has a lightweight SQLite audit log for scan lifecycle, job/artifact reads, action reads, and action updates. Full workgroup permissions, role-based access, membership tables, matter-level assignments, and immutable production audit retention are future work.

## API Endpoints

Core endpoints currently include:

```text
GET  /health
GET  /docs
GET  /openapi.json
GET  /api-docs
GET  /api/v1/docs/api.md
GET  /api/v1/docs/endpoints
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
GET  /api/v1/audit/events
POST /api/v1/documents/redact-text
```

## Anchor Capability Profiles

Anchor detection is gated by explicit capability profiles. Ruleset names provide the default profile, and requests may narrow capabilities with `enabled_anchors`.

```text
v0.1 / v0.1.1: text, missing, risk, context
v0.2: text, missing, risk, context, semantic_candidate, semantic, escalation
v0.3: text, missing, risk, context, semantic_candidate, semantic, escalation, obligation, relation
v1.0: v0.3 plus action
```

Request controls:

```text
anchor_profile=v0.1|v0.1.1|v0.2|v0.3|v1.0
enabled_anchors=text,missing,risk,context,semantic,escalation,obligation,relation,action
semantic_validation=candidate|validate|disabled
escalation_policy=default|strict|disabled
action_policy=default|disabled
```

The server should never enable anchors outside the selected profile. For example, `rules_v0.1` does not produce Semantic or Escalation Anchors even if semantic-style rules exist in an inherited or local rule file.

## Implemented Anchor Versions

### v0.1

Implemented anchor scope:

- Text Anchor
- Missing Anchor
- Risk Anchor as explicit risk metadata on findings
- lightweight Context Anchor

Notes:

- v0.1 is rule-driven and deterministic.
- v0.1 does not emit Semantic or Escalation Anchors.
- `rules_v0.1` currently contains 9 baseline general contract-review rules.
- The 9 rules are a pipeline baseline, not a lawyer-approved production rule library.

### v0.1.1

Engineering completion layer for v0.1:

- PDF layout extraction using native PyMuPDF fallback.
- Annotated PDF rendering.
- JSON report URL.
- Markdown report URL.
- Annotated PDF URL.
- Scoped artifact access.

Validated previously by unit tests and HTTP smoke tests, but not final product/legal acceptance.

### v0.2

Implemented anchor scope:

- Semantic Candidate
- confirmed Semantic Anchor through local validation
- explicit Escalation Anchor
- review queue metadata

Key files:

- `server/app/services/semantic_validator.py`
- `server/app/services/escalation_policy.py`
- `server/rules/rules_v0.2.yaml`

Important behavior:

- `rules_v0.2` extends `rules_v0.1`.
- Semantic validation is currently local/deterministic and auditable.
- External LLM routing is future work.
- Escalation Anchors are emitted as separate review-routing records, not only nested fields inside risk metadata.

### v0.3

Implemented anchor scope:

- Obligation Anchor
- Relation Anchor

Key files:

- `server/rules/rules_v0.3.yaml`
- `server/app/services/anchor_engine.py`
- `server/app/services/report_service.py`

Important behavior:

- `rules_v0.3` extends `rules_v0.2`.
- `type: obligation` rules produce `obligation_anchors`.
- `type: relation` rules produce `relation_anchors`.
- Summary includes `obligation_anchors` and `relation_anchors` counts.
- Markdown reports include Obligation and Relation sections.
- Semantic validation preserves v0.3 summary counts.

Current v0.3 rule coverage includes baseline obligations for payment, notice, data return/deletion, security incident notice, delivery/acceptance, audit cooperation, confidentiality survival, insurance, compliance with laws, and subcontractor flowdown.

Current v0.3 relation coverage includes termination/data-return dependency, SLA/service-credit dependency, payment/suspension dependency, confidentiality/residual-knowledge exception, security incident/remediation dependency, subprocessor/customer-data dependency, acceptance/payment dependency, and audit/records dependency.

### v1.0

Implemented anchor scope:

- Action Anchor

Key files:

- `server/rules/rules_v1.0.yaml`
- `server/app/services/action_anchor.py`
- `server/app/api/routes_contract.py`
- `server/app/services/report_service.py`

Important behavior:

- `rules_v1.0` extends `rules_v0.3`.
- Action Anchors are generated after grounding, semantic validation, escalation policy, obligation extraction, and relation extraction.
- `action_anchors` contain proposed legal-review actions with source anchor metadata, action type, priority, owner role, due policy, status, and recommendation.
- `action_queue` provides lightweight queue metadata for future workflow integration.
- `action_policy=default|disabled` controls whether actions are emitted when the action capability is enabled.
- Current runtime endpoints allow the creating scope to list actions and update action status to `proposed`, `accepted`, `in_progress`, `completed`, or `dismissed`.
- Action updates mutate the persisted job result JSON and update matching action queue item status.
- This is a runnable Action Anchor bridge with minimal status workflow, not a full production task/workflow engine.

### Runtime Audit Logs

Implemented lightweight audit scope:

- SQLite-backed `audit_events` table.
- Scoped by `user_id`, `organization_id`, and `workspace_id`.
- Records scan creation/completion/failure, job reads, artifact reads, action reads, and action status updates.
- Query endpoint: `GET /api/v1/audit/events` with optional `resource_type`, `resource_id`, and `limit`.

This is development-grade auditability. Production-grade immutable audit retention, role-based auditor access, and centralized log export remain future work.

## Rule Assets

Rules are a core legal knowledge asset, not ordinary configuration.

Current rule files:

```text
server/rules/rules_v0.1.yaml
server/rules/rules_v0.2.yaml
server/rules/rules_v0.3.yaml
server/rules/rules_v1.0.yaml
server/rules/industry_configs/construction.yaml
```

Rule loader behavior:

- Supports ruleset inheritance with `extends`.
- Supports industry overlays through `industry_id`.
- Supports org overlays through `org_id` and `server/rules/org_configs/` when files exist.
- Filters out rules with `enabled: false`.

Known product direction:

- Add personalized rule add/delete/edit/test/version tooling later.
- Rule scopes should eventually include platform baseline, industry pack, company playbook, workspace/matter, team shared, and personal lawyer rules.
- Personal rules should be exportable/importable where permissions allow.
- Promotion from personal rules to team/company rules should require review and approval.

## Important Services

- `server/app/services/anchor_capabilities.py`: profile and enabled-anchor gatekeeping.
- `server/app/services/action_anchor.py`: v1.0 proposed Action Anchor and action queue generation.
- `server/app/services/audit_log.py`: SQLite audit event persistence and scoped event listing.
- `server/app/services/anchor_engine.py`: core scan engine for text, missing, semantic candidates, obligation, relation, summary building.
- `server/app/services/semantic_validator.py`: local v0.2 semantic validation and summary recalculation.
- `server/app/services/escalation_policy.py`: explicit Escalation Anchor and review queue generation.
- `server/app/services/rule_loader.py`: ruleset inheritance and overlays.
- `server/app/services/document_service.py`: upload saving and extraction coordination.
- `server/app/services/docling_extractor.py`: optional Docling extraction.
- `server/app/services/langextract_grounding.py`: LangExtract/local grounding.
- `server/app/services/layout_index.py`: PDF text/layout map.
- `server/app/services/pdf_renderer.py`: annotated PDF rendering.
- `server/app/services/report_service.py`: JSON/Markdown report persistence.
- `server/app/services/job_store.py`: SQLite jobs.
- `server/app/services/access_control.py`: lightweight scope isolation.

## Testing State

The test suite lives mainly in:

```text
server/tests/test_anchor_engine.py
```

It covers:

- v0.1 keyword anchors.
- Missing Anchors.
- Negation suppression.
- v0.1/v0.2/v0.3/v1.0 capability separation.
- v0.2 ruleset inheritance and baseline semantic rules.
- v0.2 Semantic validation and Escalation Anchors.
- v0.3 Obligation and Relation Anchors.
- v0.3 summary preservation after semantic validation.
- v1.0 Action Anchor generation and action capability gating.
- AuditLogStore scoped event recording/listing.
- `enabled_anchors` narrowing.
- Industry overlay rules.
- Local exact grounding.
- DocumentService native fallback.
- PDF renderer creation.
- Lawyer/workspace access isolation.

Latest expected test command:

```bash
cd /Users/lq/projects/laws/lexAnchor/server
PYTHONDONTWRITEBYTECODE=1 HTTP_PROXY=http://127.0.0.1:51809 HTTPS_PROXY=http://127.0.0.1:51809 UV_HTTP_TIMEOUT=120 uv run --python 3.11 python -m unittest
```

At the time lightweight audit logs and action status endpoints were added, the command above passed with 23 tests.

## Known Limitations

- No final product acceptance has been performed.
- No final legal-domain/lawyer acceptance has been performed.
- Current rule packs are baseline test and pipeline rules, not a complete legal rule library.
- Semantic validation is local and deterministic; real LLM/model routing remains future work.
- Relation Anchors are currently trigger-based and shallow; future versions should build richer clause graphs.
- Obligation Anchors are currently trigger-based; future versions should extract actor, action, object, deadline, condition, exception, and consequence.
- Action Anchors now have minimal persisted status updates inside job result JSON, but there is no durable standalone workflow/task engine yet.
- Access isolation is header-based development isolation; production auth/RBAC is future work.
- SQLite/local filesystem are development storage choices; PostgreSQL/object storage are the v1.0 direction.
- Async scan uses FastAPI background tasks, not a durable queue.

## Roadmap Direction

Near-term next work:

- Keep the 23-test suite passing as v1.0 action workflow fields expand.
- Add richer v0.3 obligation extraction fields: actor, action, object, deadline, condition, consequence.
- Add richer relation graph fields and relation endpoint/query support.
- Add more industry and company rule packs.
- Expand Action Anchors into persisted workflow actions, approval gates, and reviewer assignment.

v1.0 direction:

- Action Anchor.
- Workflow actions and approval gates.
- Review collaboration.
- PostgreSQL schema for organizations, users, memberships, workspaces, matters, documents, artifacts, anchor runs, findings, rulesets, comments, decisions, and actions.
- Object storage.
- Durable queue workers.
- RBAC and audit logs.
- Personalized and company-specific rule management.
