# LexAnchor Server

Server-side backend for LexAnchor anchor tools. This package turns the current contract review POC into an API service for legal teams, documents, redaction, anchor scans, reports, and future workflow actions.

## v0.1 Scope

- FastAPI API service.
- SQLite job store.
- Local document and artifact storage.
- Text and file contract scan endpoints.
- Ruleset inspection endpoints.
- Text, missing, risk, and context anchors.
- Lightweight redaction preview endpoint.
- Markdown and JSON reports.

## Anchor Capability Profiles

Anchor finding is gated by explicit capability profiles. The ruleset name provides the default profile, and requests can narrow the enabled anchors with `enabled_anchors`.

```text
v0.1 / v0.1.1: text, missing, risk, context
v0.2: text, missing, risk, context, semantic_candidate, semantic, escalation
v0.3: v0.2 plus obligation and relation
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

The server never enables anchors outside the selected profile. For example, `rules_v0.1` does not produce Semantic or Escalation Anchors even if semantic-style rules exist in the file.

## Run

```bash
cd lexAnchor/server
HTTP_PROXY=http://127.0.0.1:51809 HTTPS_PROXY=http://127.0.0.1:51809 UV_HTTP_TIMEOUT=120 uv sync
uv run uvicorn app.main:app --reload --port 8010
```

For the full document and grounding integrations:

```bash
cd lexAnchor/server
HTTP_PROXY=http://127.0.0.1:51809 HTTPS_PROXY=http://127.0.0.1:51809 UV_HTTP_TIMEOUT=120 uv sync --extra integrations
LEXANCHOR_EXTRACTION_BACKEND=auto LEXANCHOR_GROUNDING_BACKEND=auto uv run uvicorn app.main:app --reload --port 8010
```

Integration controls:

```text
LEXANCHOR_EXTRACTION_BACKEND=auto|docling|native
LEXANCHOR_GROUNDING_BACKEND=auto|langextract|disabled
LANGEXTRACT_ENABLED=auto|true|false
LANGEXTRACT_API_KEY=...
GOOGLE_API_KEY=...
```

## Test

```bash
cd lexAnchor/server
HTTP_PROXY=http://127.0.0.1:51809 HTTPS_PROXY=http://127.0.0.1:51809 UV_HTTP_TIMEOUT=120 uv run --python 3.11 python -m unittest
```

## Core Endpoints

```text
GET  /health
GET  /docs
GET  /openapi.json
GET  /api-docs
GET  /api/v1/docs/api.md
GET  /api/v1/docs/endpoints
GET  /api/v1/rulesets
GET  /api/v1/rulesets/rules_v0.1
GET  /api/v1/rulesets/rules_v0.2
GET  /api/v1/rulesets/rules_v0.3
GET  /api/v1/rulesets/rules_v1.0
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

## Access Isolation

The current development server uses request-scope headers to isolate legal-team objects before a full authentication provider is added:

```text
X-User-Id: lawyer_a
X-Organization-Id: acme_legal
X-Workspace-Id: procurement
```

Every scan job is bound to the creating `user_id`, `organization_id`, and `workspace_id`. Job metadata and artifacts return `404` when requested from a different scope, so one lawyer cannot read another lawyer's files or reports by guessing a `job_id`.

## HTTP API Docs

After starting the service, open:

```text
http://127.0.0.1:8010/api-docs
```

Other documentation formats are also served by the API:

```text
http://127.0.0.1:8010/docs
http://127.0.0.1:8010/openapi.json
http://127.0.0.1:8010/api/v1/docs/api.md
http://127.0.0.1:8010/api/v1/docs/endpoints
```

## Example

```bash
curl -s http://127.0.0.1:8010/api/v1/contract/scan-text \
  -H 'x-user-id: lawyer_a' \
  -H 'x-organization-id: acme_legal' \
  -H 'x-workspace-id: procurement' \
  -H 'content-type: application/json' \
  -d '{"text":"This agreement shall automatically renew and includes unlimited liability.","industry_id":"construction"}'
```

v0.2 Semantic and Escalation Anchor scan:

```bash
curl -s http://127.0.0.1:8010/api/v1/contract/scan-text \
  -H 'x-user-id: lawyer_a' \
  -H 'x-organization-id: acme_legal' \
  -H 'x-workspace-id: procurement' \
  -H 'content-type: application/json' \
  -d '{"ruleset":"rules_v0.2","semantic_validation":"validate","escalation_policy":"default","text":"All intellectual property in the work product belongs to Vendor."}'
```

v0.3 Obligation and Relation Anchor scan:

```bash
curl -s http://127.0.0.1:8010/api/v1/contract/scan-text \
  -H 'x-user-id: lawyer_a' \
  -H 'x-organization-id: acme_legal' \
  -H 'x-workspace-id: procurement' \
  -H 'content-type: application/json' \
  -d '{"ruleset":"rules_v0.3","text":"Upon termination, Vendor shall return data within 30 days. The service level includes a service credit."}'
```

v1.0 Action Anchor scan:

```bash
curl -s http://127.0.0.1:8010/api/v1/contract/scan-text \
  -H 'x-user-id: lawyer_a' \
  -H 'x-organization-id: acme_legal' \
  -H 'x-workspace-id: procurement' \
  -H 'content-type: application/json' \
  -d '{"ruleset":"rules_v1.0","action_policy":"default","text":"Upon termination, Vendor shall return data within 30 days. This agreement includes unlimited liability."}'
```

Minimal v1.0 action workflow:

```bash
curl -s http://127.0.0.1:8010/api/v1/jobs/{job_id}/actions \
  -H 'x-user-id: lawyer_a' \
  -H 'x-organization-id: acme_legal' \
  -H 'x-workspace-id: procurement'

curl -s -X PATCH http://127.0.0.1:8010/api/v1/jobs/{job_id}/actions/{action_id} \
  -H 'x-user-id: lawyer_a' \
  -H 'x-organization-id: acme_legal' \
  -H 'x-workspace-id: procurement' \
  -H 'content-type: application/json' \
  -d '{"status":"completed","decision":"accepted","comment":"Reviewed by counsel."}'

curl -s 'http://127.0.0.1:8010/api/v1/audit/events?resource_type=job&resource_id={job_id}' \
  -H 'x-user-id: lawyer_a' \
  -H 'x-organization-id: acme_legal' \
  -H 'x-workspace-id: procurement'
```

Audit logs are stored in SQLite and scoped by `user_id`, `organization_id`, and `workspace_id`. Current audit coverage includes scan lifecycle events, job/artifact reads, action reads, and action status updates.

The server result is an initial review aid and does not constitute final legal advice.

## Docling and LangExtract

- `docling` is integrated into the server document extraction chain. In `auto` mode it is used when installed and supported by the file type; otherwise the native PDF/DOCX/text extraction path is used.
- `langextract` is integrated into the anchor grounding chain. In `auto` mode it uses LangExtract when network/API-key settings allow it; otherwise the server falls back to local exact-string grounding.
- Per-request overrides are available through `extraction_backend` and `grounding_backend` on scan APIs.

## v0.1.1 PDF Artifacts

PDF scans now attempt to produce an annotated PDF artifact when native PDF layout information is available:

```text
GET /api/v1/jobs/{job_id}/annotated.pdf
```

The scan response includes `artifacts.annotated_pdf_url` and `artifacts.annotated_pdf_path` when rendering succeeds.
