from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

router = APIRouter(tags=["api-docs"])

ENDPOINTS = [
    {
        "method": "GET",
        "path": "/health",
        "summary": "Service health check.",
        "request": None,
        "response": "Service status and storage path.",
    },
    {
        "method": "GET",
        "path": "/docs",
        "summary": "Interactive Swagger UI generated from OpenAPI.",
        "request": None,
        "response": "HTML API console.",
    },
    {
        "method": "GET",
        "path": "/openapi.json",
        "summary": "Machine-readable OpenAPI schema.",
        "request": None,
        "response": "OpenAPI JSON document.",
    },
    {
        "method": "GET",
        "path": "/api-docs",
        "summary": "LexAnchor human-readable API guide.",
        "request": None,
        "response": "HTML API guide.",
    },
    {
        "method": "GET",
        "path": "/api/v1/docs/api.md",
        "summary": "LexAnchor API guide as Markdown.",
        "request": None,
        "response": "Markdown API guide.",
    },
    {
        "method": "GET",
        "path": "/api/v1/docs/endpoints",
        "summary": "Machine-readable endpoint index.",
        "request": None,
        "response": "JSON endpoint catalog.",
    },
    {
        "method": "GET",
        "path": "/api/v1/rulesets",
        "summary": "List available rulesets.",
        "request": None,
        "response": "Ruleset names, versions, and rule counts.",
    },
    {
        "method": "GET",
        "path": "/api/v1/rulesets/{ruleset_id}",
        "summary": "Inspect one ruleset, optionally with industry or organization overlays.",
        "request": "Query: industry_id, org_id.",
        "response": "Resolved ruleset metadata and rules.",
    },
    {
        "method": "POST",
        "path": "/api/v1/sessions/dev-login",
        "summary": "Create a development session token for a user, organization, and workspace scope.",
        "request": "JSON body with user_id, organization_id, workspace_id, roles, ttl_hours.",
        "response": "Bearer session token and expiry metadata.",
    },
    {
        "method": "GET",
        "path": "/api/v1/sessions/me",
        "summary": "Read the current session-derived request scope.",
        "request": "Authorization: Bearer token or development headers.",
        "response": "Current user, organization, workspace, roles, and authentication state.",
    },
    {
        "method": "DELETE",
        "path": "/api/v1/sessions/current",
        "summary": "Revoke the current session token.",
        "request": "Authorization: Bearer token or X-LexAnchor-Session.",
        "response": "Revocation confirmation.",
    },
    {
        "method": "POST",
        "path": "/api/v1/memberships/dev-grant",
        "summary": "Grant or update a user membership for minimal RBAC.",
        "request": "JSON body with user_id, organization_id, workspace_id, roles, status.",
        "response": "Membership record.",
    },
    {
        "method": "GET",
        "path": "/api/v1/memberships",
        "summary": "List memberships visible to the current manager scope.",
        "request": "Query: organization_id, workspace_id, limit.",
        "response": "Membership records.",
    },
    {
        "method": "POST",
        "path": "/api/v1/contract/scan-text",
        "summary": "Run a synchronous text scan and return anchors plus report URLs.",
        "request": "JSON body with text, ruleset, anchor_profile, enabled_anchors, semantic_validation, escalation_policy, action_policy, industry_id, org_id, organization_id, workspace_id, grounding_backend.",
        "response": "Completed job response with result, JSON report URL, and Markdown report URL.",
    },
    {
        "method": "POST",
        "path": "/api/v1/contract/scan",
        "summary": "Upload and synchronously scan a document.",
        "request": "multipart/form-data: file, ruleset, anchor_profile, enabled_anchors, semantic_validation, escalation_policy, action_policy, industry_id, org_id, organization_id, workspace_id, extraction_backend, grounding_backend.",
        "response": "Completed job response with result and report URLs.",
    },
    {
        "method": "POST",
        "path": "/api/v1/contract/scan-async",
        "summary": "Upload and queue a document scan.",
        "request": "multipart/form-data: file, ruleset, anchor_profile, enabled_anchors, semantic_validation, escalation_policy, action_policy, industry_id, org_id, organization_id, workspace_id, extraction_backend, grounding_backend.",
        "response": "Queued job response.",
    },
    {
        "method": "GET",
        "path": "/api/v1/jobs/{job_id}",
        "summary": "Read job status and result metadata.",
        "request": None,
        "response": "Job status, progress, request, result, and error fields.",
    },
    {
        "method": "GET",
        "path": "/api/v1/jobs/{job_id}/report.json",
        "summary": "Download a job JSON report.",
        "request": None,
        "response": "JSON report artifact.",
    },
    {
        "method": "GET",
        "path": "/api/v1/jobs/{job_id}/report.md",
        "summary": "Download a job Markdown report.",
        "request": None,
        "response": "Markdown report artifact.",
    },
    {
        "method": "GET",
        "path": "/api/v1/jobs/{job_id}/annotated.pdf",
        "summary": "Download a PDF scan's annotated PDF artifact when available.",
        "request": None,
        "response": "Annotated PDF artifact.",
    },
    {
        "method": "GET",
        "path": "/api/v1/jobs/{job_id}/actions",
        "summary": "List proposed Action Anchors for a job.",
        "request": None,
        "response": "Action policy, action queue, and action anchors.",
    },
    {
        "method": "PATCH",
        "path": "/api/v1/jobs/{job_id}/actions/{action_id}",
        "summary": "Update an Action Anchor status for the current reviewer scope.",
        "request": "JSON body with status, optional decision, and optional comment.",
        "response": "Updated action and action queue metadata.",
    },
    {
        "method": "GET",
        "path": "/api/v1/jobs/{job_id}/audit-events",
        "summary": "List audit events for a job after scoped access checks.",
        "request": "Query: limit.",
        "response": "Job-scoped audit event list.",
    },
    {
        "method": "GET",
        "path": "/api/v1/audit/events",
        "summary": "List audit events visible to the current request scope.",
        "request": "Query: resource_type, resource_id, limit.",
        "response": "Scoped audit event list.",
    },
    {
        "method": "POST",
        "path": "/api/v1/rule-authoring/draft-from-text",
        "summary": "Generate disabled, lawyer-reviewable rule drafts from guidance text.",
        "request": "JSON body with guide_text, rule_scope, scope_id, source_name, and max_rules.",
        "response": "Rule draft id, generated rules, warnings, and review checklist.",
    },
    {
        "method": "GET",
        "path": "/api/v1/rule-authoring/lawyer-ui-recommendations",
        "summary": "Return structured recommendations for a lawyer operation interface and server hardening.",
        "request": None,
        "response": "Primary views, workflow steps, UI principles, and server hardening priorities.",
    },
    {
        "method": "POST",
        "path": "/api/v1/documents/redact-text",
        "summary": "Preview text redaction for common sensitive fields.",
        "request": "JSON body with text, mask, detect_names.",
        "response": "Redacted text, findings, and summary counts.",
    },
]


@router.get("/api-docs", response_class=HTMLResponse)
def api_docs_page(request: Request) -> HTMLResponse:
    base_url = str(request.base_url).rstrip("/")
    markdown = build_api_markdown(base_url=base_url)
    html = markdown_to_simple_html(markdown)
    return HTMLResponse(html)


@router.get("/api/v1/docs/api.md", response_class=PlainTextResponse)
def api_docs_markdown(request: Request) -> PlainTextResponse:
    base_url = str(request.base_url).rstrip("/")
    return PlainTextResponse(build_api_markdown(base_url=base_url), media_type="text/markdown; charset=utf-8")


@router.get("/api/v1/docs/endpoints")
def api_docs_endpoints(request: Request) -> JSONResponse:
    base_url = str(request.base_url).rstrip("/")
    return JSONResponse({"base_url": base_url, "endpoints": ENDPOINTS})


def build_api_markdown(*, base_url: str) -> str:
    endpoint_rows = "\n".join(
        f"| `{item['method']}` | `{item['path']}` | {item['summary']} |" for item in ENDPOINTS
    )
    return f"""# LexAnchor Server API

Base URL: `{base_url}`

LexAnchor Server exposes document intake, text scanning, redaction, ruleset inspection, job reports, and API documentation endpoints for legal-team anchor workflows.

## Access Isolation Headers

Current development builds use request-scope headers until a full auth provider is installed:

```text
X-User-Id: lawyer_a
X-Organization-Id: acme_legal
X-Workspace-Id: procurement
```

Scan jobs and artifacts are bound to the creating scope. Reads from another scope return 404.

## Session Tokens

The server supports lightweight SQLite-backed session tokens. Tokens are returned once and stored as hashes. Send them as `Authorization: Bearer ...` or `X-LexAnchor-Session`. Development scope headers remain as a fallback for local testing.

```bash
curl -s {base_url}/api/v1/sessions/dev-login \
    -H 'content-type: application/json' \
    -d '{{"user_id":"lawyer_a","organization_id":"acme_legal","workspace_id":"procurement","roles":["legal_reviewer","rule_author"]}}'
```

Session introspection and logout:

```text
GET    /api/v1/sessions/me
DELETE /api/v1/sessions/current
```

## Minimal RBAC

Session roles are checked against a small built-in permission matrix. Development header scopes receive the `development_header_scope` role for local compatibility.

```text
org_admin: all permissions
legal_reviewer: scan, redact, read jobs/artifacts/actions/audit/rules, update actions
rule_author: read rules, create rule drafts, read audit
auditor: read jobs/artifacts/actions/audit/rules
business_submitter: scan, redact, read own jobs/artifacts
```

This is a minimal RBAC layer. Production deployments still need persisted memberships, matter assignment, and externally authenticated identities.

Roles are now derived from SQLite membership records when creating sessions. `dev-login` bootstraps a membership only when none exists for the requested user/org/workspace. Managers can grant or update memberships through `POST /api/v1/memberships/dev-grant`.

## Built-in Docs

- Swagger UI: `{base_url}/docs`
- OpenAPI JSON: `{base_url}/openapi.json`
- LexAnchor HTML guide: `{base_url}/api-docs`
- LexAnchor Markdown guide: `{base_url}/api/v1/docs/api.md`
- Endpoint index JSON: `{base_url}/api/v1/docs/endpoints`

## Endpoint Index

| Method | Path | Summary |
| --- | --- | --- |
{endpoint_rows}

## Example: Scan Text

```bash
curl -s {base_url}/api/v1/contract/scan-text \\
    -H 'x-user-id: lawyer_a' \\
    -H 'x-organization-id: acme_legal' \\
    -H 'x-workspace-id: procurement' \\
  -H 'content-type: application/json' \\
  -d '{{"text":"This agreement shall automatically renew and includes unlimited liability.","ruleset":"rules_v0.1","industry_id":"construction"}}'
```

## Integration Controls

Anchor capability controls:

```text
anchor_profile: v0.1 | v0.1.1 | v0.2 | v0.3 | v1.0
enabled_anchors: comma-separated subset, for example text,missing,risk,context,semantic,obligation,relation,action
semantic_validation: candidate | validate | disabled
escalation_policy: default | strict | disabled
action_policy: default | disabled
```

The ruleset name supplies the default profile. `rules_v0.1` only enables Text, Missing, Risk, and Context Anchors. `rules_v0.2` enables Semantic Candidate, Semantic, and Escalation Anchors in addition to the v0.1 anchors. `rules_v0.3` adds Obligation and Relation Anchors. `rules_v1.0` adds Action Anchors. Requests can narrow a profile, but cannot enable anchors outside the selected version.

```text
extraction_backend: auto | docling | native
grounding_backend: auto | langextract | disabled
```

Server environment variables:

```text
LEXANCHOR_EXTRACTION_BACKEND=auto|docling|native
LEXANCHOR_GROUNDING_BACKEND=auto|langextract|disabled
LANGEXTRACT_ENABLED=auto|true|false
LANGEXTRACT_API_KEY=...
GOOGLE_API_KEY=...
```

Docling is used for document conversion when installed and selected. LangExtract is used for exact evidence grounding when network/API-key settings allow it; otherwise the server falls back to local exact-string grounding.

## Rule Authoring

The rule-authoring endpoint converts lawyer guidance text into disabled LexAnchor rule drafts. Drafts are review artifacts, not automatically activated production rules.

```bash
curl -s {base_url}/api/v1/rule-authoring/draft-from-text \
    -H 'x-user-id: lawyer_a' \
    -H 'x-organization-id: acme_legal' \
    -H 'x-workspace-id: procurement' \
    -H 'content-type: application/json' \
    -d '{{"rule_scope":"company","scope_id":"acme_playbook","guide_text":"合同不得包含无限责任或 unlimited liability。涉及客户数据和训练模型的条款必须升级审核。"}}'
```

UI planning support:

```text
GET /api/v1/rule-authoring/lawyer-ui-recommendations
```

## Example: Redact Text

```bash
curl -s {base_url}/api/v1/documents/redact-text \\
  -H 'content-type: application/json' \\
  -d '{{"text":"Contact zhangsan@example.com or 13800138000.","detect_names":true}}'
```

## v0.1 Anchor Scope

v0.1 returns Text Anchors, Missing Anchors, Risk Anchors, and lightweight Context Anchors. LangExtract is used for evidence grounding when available; Semantic and Escalation Anchors are reserved for v0.2. Results are first-pass review evidence and do not constitute final legal advice.

## v0.2 Anchor Scope

v0.2 adds explicit Semantic Anchors and Escalation Anchors. Semantic candidates can be locally validated into confirmed Semantic Anchors. Escalation Anchors are emitted as separate review-routing records instead of only nested metadata inside risk findings.

## v0.3 Anchor Scope

v0.3 adds Obligation Anchors and Relation Anchors. Obligation Anchors identify duties such as payment, notice, data return/deletion, and security incident notice. Relation Anchors identify cross-clause dependencies such as termination triggering data-return obligations or SLA commitments linking to service-credit remedies.

## v1.0 Anchor Scope

v1.0 adds Action Anchors. Action Anchors convert review evidence, escalations, obligations, and relation dependencies into proposed legal-review actions with priority, owner role, due policy, status, and action queue metadata. This is a first workflow bridge, not a full production workflow engine.

Minimal v1.0 runtime endpoints allow the creating lawyer scope to read proposed actions and update status to `proposed`, `accepted`, `in_progress`, `completed`, or `dismissed`. Scan lifecycle events, job/artifact reads, action reads, and action updates are recorded in scoped audit logs.

```text
GET   /api/v1/jobs/{{job_id}}/actions
PATCH /api/v1/jobs/{{job_id}}/actions/{{action_id}}
GET   /api/v1/jobs/{{job_id}}/audit-events
GET   /api/v1/audit/events?resource_type=job&resource_id={{job_id}}
```

## v0.1.1 Artifact Loop

For PDF scans, the server now attempts to generate:

```text
JSON report: /api/v1/jobs/{{job_id}}/report.json
Markdown report: /api/v1/jobs/{{job_id}}/report.md
Annotated PDF: /api/v1/jobs/{{job_id}}/annotated.pdf
```
"""


def markdown_to_simple_html(markdown: str) -> str:
    lines = markdown.splitlines()
    body_parts: list[str] = []
    in_code = False
    in_table = False
    table_rows: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip()
        if line.startswith("```"):
            if not in_code:
                in_code = True
                body_parts.append("<pre><code>")
            else:
                in_code = False
                body_parts.append("</code></pre>")
            continue
        if in_code:
            body_parts.append(escape_html(line) + "\n")
            continue

        if line.startswith("| "):
            in_table = True
            table_rows.append(line)
            continue
        if in_table:
            body_parts.append(render_markdown_table(table_rows))
            table_rows = []
            in_table = False

        if line.startswith("# "):
            body_parts.append(f"<h1>{escape_html(line[2:])}</h1>")
        elif line.startswith("## "):
            body_parts.append(f"<h2>{escape_html(line[3:])}</h2>")
        elif line.startswith("- "):
            body_parts.append(f"<p>{render_inline(line)}</p>")
        elif line:
            body_parts.append(f"<p>{render_inline(line)}</p>")

    if table_rows:
        body_parts.append(render_markdown_table(table_rows))

    body = "\n".join(body_parts)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LexAnchor Server API</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px auto; max-width: 1040px; padding: 0 20px; line-height: 1.55; color: #172026; }}
    h1 {{ margin-bottom: 8px; }}
    h2 {{ margin-top: 32px; border-bottom: 1px solid #d7dde2; padding-bottom: 6px; }}
    code {{ background: #f4f6f8; padding: 2px 5px; border-radius: 4px; }}
    pre {{ background: #111827; color: #f9fafb; padding: 16px; overflow-x: auto; border-radius: 6px; }}
    pre code {{ background: transparent; padding: 0; }}
    table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }}
    th, td {{ border: 1px solid #d7dde2; padding: 8px 10px; vertical-align: top; }}
    th {{ background: #f4f6f8; text-align: left; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def render_markdown_table(rows: list[str]) -> str:
    parsed = [[cell.strip() for cell in row.strip("|").split("|")] for row in rows]
    if len(parsed) < 2:
        return ""
    header = parsed[0]
    data_rows = parsed[2:] if len(parsed) > 2 else []
    header_html = "".join(f"<th>{render_inline(cell)}</th>" for cell in header)
    rows_html = []
    for row in data_rows:
        rows_html.append("<tr>" + "".join(f"<td>{render_inline(cell)}</td>" for cell in row) + "</tr>")
    return "<table><thead><tr>" + header_html + "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table>"


def render_inline(value: str) -> str:
    escaped = escape_html(value)
    return escaped.replace("`", "")


def escape_html(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
