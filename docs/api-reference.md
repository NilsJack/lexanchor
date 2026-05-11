# LexAnchor API 完整说明与 Use Case

本文档按当前已实现功能整理。它面向三类调用方：法律团队前端、自动化 agent、以及后端/测试脚本。

当前服务器能力包括：session token、membership-backed RBAC、合同文本/文件扫描、规则集查看、报告下载、PDF 批注产物、Action Anchor 状态流转、审计日志、规则草案生成、文本脱敏预览、以及面向律师工作台的 UI 建议数据。

如果接手人是法律背景、负责前端产品和页面落地，请先读 [frontend-quickstart-for-legal.md](frontend-quickstart-for-legal.md)。那份文档从锚点概念、律师工作流、竞品差异和前端信息架构讲起。

## 1. 基础信息

开发服务默认地址：

```text
http://127.0.0.1:8010
```

启动命令：

```bash
cd /Users/lq/projects/laws/lexAnchor/server
PYTHONDONTWRITEBYTECODE=1 HTTP_PROXY=http://127.0.0.1:51809 HTTPS_PROXY=http://127.0.0.1:51809 UV_HTTP_TIMEOUT=120 uv run --python 3.11 uvicorn app.main:app --host 127.0.0.1 --port 8010
```

本地 curl 建议绕过代理：

```bash
export NO_PROXY=127.0.0.1,localhost
```

## 2. 认证、隔离与权限

### 2.1 推荐认证方式

当前推荐先创建 session，再用 bearer token 调用业务 API：

```text
Authorization: Bearer {session_token}
```

也支持替代 header：

```text
X-LexAnchor-Session: {session_token}
```

### 2.2 开发 header fallback

本地开发仍支持 scope header。使用这些 header 时，请求自动获得 `development_header_scope`，拥有全部权限，方便 smoke test：

```text
X-User-Id: lawyer_a
X-Organization-Id: acme_legal
X-Workspace-Id: procurement
```

这不是生产认证方案。

### 2.3 当前角色与权限

| Role | 用途 | 权限摘要 |
| --- | --- | --- |
| `org_admin` | 组织管理员 | 全部权限 |
| `workspace_manager` | 工作区管理员 | 扫描、脱敏、读 job/artifact/action/audit/rules、更新 action、创建 rule draft、读写 membership |
| `legal_reviewer` | 律师审查员 | 扫描、脱敏、读 job/artifact/action/audit/rules、更新 action |
| `rule_author` | 规则作者 | 读 rules、创建 rule draft、读 audit |
| `auditor` | 审计员 | 读 job/artifact/action/audit/rules |
| `business_submitter` | 业务提交人 | 扫描、脱敏、读自己的 job/artifact |
| `development_header_scope` | 本地开发 fallback | 全部权限 |

### 2.4 对象隔离规则

Job、report、artifact、action、job audit 读取都按 `created_by + organization_id + workspace_id` 做隔离。不同 scope 访问会返回 `404`，避免通过 job id 猜测对象是否存在。

Membership 目前是 organization/workspace 级，还没有 matter/project assignment。

## 3. API 总览

| Method | Path | 权限 | 主要 use case |
| --- | --- | --- | --- |
| `GET` | `/health` | 无 | 服务探活 |
| `GET` | `/docs` | 无 | Swagger UI |
| `GET` | `/openapi.json` | 无 | OpenAPI schema |
| `GET` | `/api-docs` | 无 | HTML API 说明 |
| `GET` | `/api/v1/docs/api.md` | 无 | Markdown API 说明 |
| `GET` | `/api/v1/docs/endpoints` | 无 | 机器可读端点目录 |
| `POST` | `/api/v1/sessions/dev-login` | 无 | 创建开发 session |
| `GET` | `/api/v1/sessions/me` | session 或 fallback | 查看当前 scope/roles |
| `DELETE` | `/api/v1/sessions/current` | session token | 注销当前 session |
| `POST` | `/api/v1/memberships/dev-grant` | `membership:write` | 创建/更新 workspace membership |
| `GET` | `/api/v1/memberships` | `membership:read` | 查看 membership 列表 |
| `GET` | `/api/v1/rulesets` | `rule:read` | 列出规则集 |
| `GET` | `/api/v1/rulesets/{ruleset_id}` | `rule:read` | 查看规则集与 overlay 结果 |
| `POST` | `/api/v1/contract/scan-text` | `contract:scan` | 同步扫描文本 |
| `POST` | `/api/v1/contract/scan` | `contract:scan` | 同步上传并扫描文件 |
| `POST` | `/api/v1/contract/scan-async` | `contract:scan` | 上传文件并后台扫描 |
| `GET` | `/api/v1/jobs/{job_id}` | `job:read` | 查看 job 状态和扫描结果 |
| `GET` | `/api/v1/jobs/{job_id}/report.json` | `artifact:read` | 下载 JSON 报告 |
| `GET` | `/api/v1/jobs/{job_id}/report.md` | `artifact:read` | 下载 Markdown 报告 |
| `GET` | `/api/v1/jobs/{job_id}/annotated.pdf` | `artifact:read` | 下载 PDF 批注件 |
| `GET` | `/api/v1/jobs/{job_id}/actions` | `action:read` | 查看 Action Anchor 队列 |
| `PATCH` | `/api/v1/jobs/{job_id}/actions/{action_id}` | `action:update` | 更新 Action Anchor 状态 |
| `GET` | `/api/v1/jobs/{job_id}/audit-events` | `audit:read` | 查看某 job 审计 |
| `GET` | `/api/v1/audit/events` | `audit:read` | 按 scope/resource 查询审计 |
| `POST` | `/api/v1/rule-authoring/draft-from-text` | `rule_draft:create` | 从律师指南生成规则草案 |
| `GET` | `/api/v1/rule-authoring/lawyer-ui-recommendations` | `rule:read` | 获取律师工作台 UI 建议 |
| `POST` | `/api/v1/documents/redact-text` | `document:redact` | 文本脱敏预览 |

## 4. API 详细说明

### 4.1 健康检查与文档

#### `GET /health`

用途：服务探活、部署检查、启动后 smoke test。

响应示例：

```json
{
  "ok": true,
  "service": "lexanchor-server",
  "version": "0.1.0",
  "storage_dir": "/path/to/storage"
}
```

#### `GET /docs`

用途：FastAPI Swagger UI，适合开发者手动调 API。

#### `GET /openapi.json`

用途：给 SDK 生成器、API 网关或测试工具读取 OpenAPI schema。

#### `GET /api-docs`

用途：LexAnchor 自带 HTML API 指南。

#### `GET /api/v1/docs/api.md`

用途：LexAnchor 自带 Markdown API 指南，适合 agent 或文档系统抓取。

#### `GET /api/v1/docs/endpoints`

用途：机器可读 endpoint catalog。

响应结构：

```json
{
  "base_url": "http://127.0.0.1:8010",
  "endpoints": [
    {
      "method": "GET",
      "path": "/health",
      "summary": "Service health check.",
      "request": null,
      "response": "Service status and storage path."
    }
  ]
}
```

### 4.2 Session API

#### `POST /api/v1/sessions/dev-login`

用途：创建开发 session token。当前 roles 优先从 membership 读取。如果没有 membership，开发模式会 bootstrap 一条 membership。

请求体：

```json
{
  "user_id": "lawyer_a",
  "organization_id": "acme_legal",
  "workspace_id": "procurement",
  "roles": ["legal_reviewer", "rule_author"],
  "ttl_hours": 12
}
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `user_id` | 是 | 当前用户 id |
| `organization_id` | 是 | 组织 id |
| `workspace_id` | 是 | 工作区 id |
| `roles` | 否 | bootstrap membership 时使用；已有 membership 时会被 membership roles 覆盖 |
| `ttl_hours` | 否 | session 有效小时数，范围 1-168，默认 12 |

响应：

```json
{
  "session_id": "sess_...",
  "session_token": "lxs_sess_...",
  "token_type": "Bearer",
  "user_id": "lawyer_a",
  "organization_id": "acme_legal",
  "workspace_id": "procurement",
  "roles": ["legal_reviewer", "rule_author"],
  "expires_at": "2026-05-04T12:00:00+00:00"
}
```

典型 curl：

```bash
curl -s http://127.0.0.1:8010/api/v1/sessions/dev-login \
  -H 'content-type: application/json' \
  -d '{"user_id":"lawyer_a","organization_id":"acme_legal","workspace_id":"procurement","roles":["legal_reviewer","rule_author"],"ttl_hours":12}'
```

#### `GET /api/v1/sessions/me`

用途：前端加载后确认当前用户、组织、工作区、roles。

请求：

```bash
curl -s http://127.0.0.1:8010/api/v1/sessions/me \
  -H "authorization: Bearer $TOKEN"
```

响应：

```json
{
  "session_id": "sess_...",
  "user_id": "lawyer_a",
  "organization_id": "acme_legal",
  "workspace_id": "procurement",
  "roles": ["legal_reviewer"],
  "authenticated": true
}
```

#### `DELETE /api/v1/sessions/current`

用途：注销当前 session，使 token 失效。

请求：

```bash
curl -s -X DELETE http://127.0.0.1:8010/api/v1/sessions/current \
  -H "authorization: Bearer $TOKEN"
```

响应：

```json
{"ok": true, "session_id": "sess_...", "revoked": true}
```

### 4.3 Membership API

#### `POST /api/v1/memberships/dev-grant`

用途：工作区管理员或开发 header scope 给用户创建/更新 membership。用于把 roles 固化到 SQLite，而不是每次登录临时传 roles。

权限：`membership:write`。

请求体：

```json
{
  "user_id": "lawyer_a",
  "organization_id": "acme_legal",
  "workspace_id": "procurement",
  "roles": ["legal_reviewer", "rule_author"],
  "status": "active"
}
```

`status` 可选：`active` 或 `disabled`。

响应：

```json
{
  "membership_id": "mbr_...",
  "user_id": "lawyer_a",
  "organization_id": "acme_legal",
  "workspace_id": "procurement",
  "roles": ["legal_reviewer", "rule_author"],
  "status": "active",
  "created_at": "2026-05-04T...",
  "updated_at": "2026-05-04T..."
}
```

开发 header 调用示例：

```bash
curl -s http://127.0.0.1:8010/api/v1/memberships/dev-grant \
  -H 'x-user-id: admin' \
  -H 'x-organization-id: acme_legal' \
  -H 'x-workspace-id: procurement' \
  -H 'content-type: application/json' \
  -d '{"user_id":"lawyer_a","organization_id":"acme_legal","workspace_id":"procurement","roles":["legal_reviewer","rule_author"]}'
```

#### `GET /api/v1/memberships`

用途：列出当前组织/工作区 membership，供管理界面或审计使用。

权限：`membership:read`。

Query：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `organization_id` | 否 | 默认当前 scope organization |
| `workspace_id` | 否 | 默认当前 scope workspace |
| `limit` | 否 | 1-500，默认 100 |

请求：

```bash
curl -s 'http://127.0.0.1:8010/api/v1/memberships?limit=100' \
  -H "authorization: Bearer $MANAGER_TOKEN"
```

响应：

```json
{"memberships": [{"membership_id": "mbr_..."}], "count": 1}
```

### 4.4 Ruleset API

#### `GET /api/v1/rulesets`

用途：列出当前可用规则集，例如 `rules_v0.1`、`rules_v0.2`、`rules_v0.3`、`rules_v1.0`。

权限：`rule:read`。

请求：

```bash
curl -s http://127.0.0.1:8010/api/v1/rulesets \
  -H "authorization: Bearer $TOKEN"
```

#### `GET /api/v1/rulesets/{ruleset_id}`

用途：查看某个规则集的规则、版本、metadata；也可指定行业或组织 overlay。

权限：`rule:read`。

Query：

| 参数 | 说明 |
| --- | --- |
| `industry_id` | 行业 overlay，例如 `construction` |
| `org_id` | 组织 overlay id |

请求：

```bash
curl -s 'http://127.0.0.1:8010/api/v1/rulesets/rules_v1.0?industry_id=construction' \
  -H "authorization: Bearer $TOKEN"
```

### 4.5 合同扫描 API

#### Anchor profile 与规则版本

| Ruleset/Profile | Anchor 能力 |
| --- | --- |
| `rules_v0.1` / `v0.1` | Text, Missing, Risk, Context |
| `v0.1.1` | v0.1 能力，加 PDF artifact loop |
| `rules_v0.2` / `v0.2` | v0.1 + Semantic Candidate, Semantic, Escalation |
| `rules_v0.3` / `v0.3` | v0.2 + Obligation, Relation |
| `rules_v1.0` / `v1.0` | v0.3 + Action |

通用控制字段：

| 字段 | 可选值 | 说明 |
| --- | --- | --- |
| `ruleset` | `rules_v0.1`/`rules_v0.2`/`rules_v0.3`/`rules_v1.0` | 选择规则文件 |
| `anchor_profile` | `v0.1`/`v0.1.1`/`v0.2`/`v0.3`/`v1.0` | 显式能力 profile |
| `enabled_anchors` | 字符串或数组 | 在 profile 内进一步收窄 anchor 类型 |
| `semantic_validation` | `candidate`/`validate`/`disabled` | 语义锚点验证模式 |
| `escalation_policy` | `default`/`strict`/`disabled` | 升级策略 |
| `action_policy` | `default`/`disabled` | Action Anchor 生成策略 |
| `industry_id` | 字符串 | 行业规则 overlay |
| `org_id` | 字符串 | 组织规则 overlay |
| `grounding_backend` | `auto`/`langextract`/`disabled` | 证据 grounding 后端 |
| `extraction_backend` | `auto`/`docling`/`native` | 文件抽取后端，仅文件扫描使用 |

#### `POST /api/v1/contract/scan-text`

用途：同步扫描粘贴文本，适合前端文本框、agent 快速检查、测试脚本。

权限：`contract:scan`。

请求体：

```json
{
  "text": "This agreement shall automatically renew and includes unlimited liability.",
  "file_name": "msa.txt",
  "document_id": "doc_001",
  "ruleset": "rules_v1.0",
  "industry_id": "construction",
  "org_id": "acme_playbook",
  "organization_id": "acme_legal",
  "workspace_id": "procurement",
  "created_by": "lawyer_a",
  "anchor_profile": "v1.0",
  "enabled_anchors": "text,missing,risk,context,semantic,escalation,obligation,relation,action",
  "semantic_validation": "validate",
  "escalation_policy": "default",
  "action_policy": "default",
  "grounding_backend": "auto",
  "return_markdown": true
}
```

使用 bearer token 时，`organization_id`、`workspace_id`、`created_by` 会由 session scope 覆盖；用开发 header 或无 header 时才主要依赖 payload/header/default scope。

响应：

```json
{
  "job_id": "job_...",
  "status": "completed",
  "result": {
    "version": "v1.0",
    "findings": [],
    "action_anchors": [],
    "action_queue": {"enabled": true, "item_count": 0, "items": []},
    "artifacts": {
      "json_report_url": "/api/v1/jobs/job_.../report.json",
      "markdown_report_url": "/api/v1/jobs/job_.../report.md"
    }
  },
  "report_url": "/api/v1/jobs/job_.../report.json",
  "markdown_report_url": "/api/v1/jobs/job_.../report.md"
}
```

curl：

```bash
curl -s http://127.0.0.1:8010/api/v1/contract/scan-text \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"ruleset":"rules_v1.0","action_policy":"default","semantic_validation":"validate","text":"Upon termination, Vendor shall return data within 30 days. This agreement includes unlimited liability."}'
```

#### `POST /api/v1/contract/scan`

用途：同步上传并扫描文件，适合小文件或用户等待结果的交互。

权限：`contract:scan`。

Content-Type：`multipart/form-data`。

Form 字段：

| 字段 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `file` | 是 | 无 | 上传文件 |
| `ruleset` | 否 | `rules_v0.1` | 规则集 |
| `industry_id` | 否 | 无 | 行业 overlay |
| `org_id` | 否 | 无 | 组织 overlay |
| `organization_id` | 否 | 当前 scope | 组织 id |
| `workspace_id` | 否 | 当前 scope | 工作区 id |
| `render_pdf` | 否 | `false` | 保留字段；PDF artifact 会在布局可用时生成 |
| `return_markdown` | 否 | `true` | 是否返回 Markdown artifact URL |
| `anchor_profile` | 否 | 由 ruleset 推导 | anchor profile |
| `enabled_anchors` | 否 | 全部 profile 能力 | 收窄 anchor 类型 |
| `extraction_backend` | 否 | server default | `auto`/`docling`/`native` |
| `grounding_backend` | 否 | server default | `auto`/`langextract`/`disabled` |
| `semantic_validation` | 否 | 自动 | 语义验证模式 |
| `escalation_policy` | 否 | 自动 | 升级策略 |
| `action_policy` | 否 | 自动 | Action 策略 |

curl：

```bash
curl -s http://127.0.0.1:8010/api/v1/contract/scan \
  -H "authorization: Bearer $TOKEN" \
  -F 'file=@/path/to/contract.pdf' \
  -F 'ruleset=rules_v1.0' \
  -F 'action_policy=default' \
  -F 'extraction_backend=auto' \
  -F 'grounding_backend=auto'
```

#### `POST /api/v1/contract/scan-async`

用途：上传文件并立即返回 queued job，后台完成扫描。适合稍大的 PDF/DOCX 或前端不想阻塞的流程。

权限：`contract:scan`。

请求字段与 `/scan` 相同。

响应：

```json
{
  "job_id": "job_...",
  "status": "queued",
  "result": null,
  "report_url": null,
  "markdown_report_url": null
}
```

前端随后轮询：

```bash
curl -s http://127.0.0.1:8010/api/v1/jobs/$JOB_ID \
  -H "authorization: Bearer $TOKEN"
```

### 4.6 Job、报告与产物 API

#### `GET /api/v1/jobs/{job_id}`

用途：读取 job 状态、progress、请求参数、扫描结果或错误。

权限：`job:read`。

响应字段：

| 字段 | 说明 |
| --- | --- |
| `job_id` | job id |
| `status` | `queued`/`running`/`completed`/`failed` |
| `progress` | 0-100 |
| `organization_id` | scope organization |
| `workspace_id` | scope workspace |
| `request` | 原始请求参数加 scope |
| `result` | 扫描结果，完成后存在 |
| `error` | 失败错误 |
| `created_at`/`updated_at` | 时间戳 |

#### `GET /api/v1/jobs/{job_id}/report.json`

用途：下载 JSON 报告。若报告文件存在返回文件，否则返回 job result JSON。

权限：`artifact:read`。

#### `GET /api/v1/jobs/{job_id}/report.md`

用途：下载 Markdown 报告。若报告尚未生成，返回 `404`。

权限：`artifact:read`。

#### `GET /api/v1/jobs/{job_id}/annotated.pdf`

用途：下载 PDF 批注件。仅 PDF 扫描且 layout map 可用时存在，否则返回 `404`。

权限：`artifact:read`。

curl：

```bash
curl -s http://127.0.0.1:8010/api/v1/jobs/$JOB_ID/report.md \
  -H "authorization: Bearer $TOKEN"
```

### 4.7 Action Anchor API

#### `GET /api/v1/jobs/{job_id}/actions`

用途：读取 v1.0 Action Anchor 队列。适合律师工作台的“待处理事项”面板。

权限：`action:read`。

响应：

```json
{
  "job_id": "job_...",
  "action_policy": {"enabled": true},
  "action_queue": {"enabled": true, "item_count": 1, "items": []},
  "action_anchors": [
    {
      "action_id": "AA-0001",
      "status": "proposed",
      "priority": "high",
      "owner_role": "legal_reviewer"
    }
  ]
}
```

#### `PATCH /api/v1/jobs/{job_id}/actions/{action_id}`

用途：律师接受、推进、完成或驳回 action。

权限：`action:update`。

请求体：

```json
{
  "status": "completed",
  "decision": "accepted",
  "comment": "Reviewed by counsel. Add liability cap before signature."
}
```

`status` 可选值：`proposed`、`accepted`、`in_progress`、`completed`、`dismissed`。

响应：

```json
{
  "job_id": "job_...",
  "action": {
    "action_id": "AA-0001",
    "status": "completed",
    "decision": "accepted",
    "comment": "Reviewed by counsel.",
    "updated_by": "lawyer_a",
    "updated_at": "2026-05-04T..."
  },
  "action_queue": {"enabled": true, "items": []}
}
```

### 4.8 Audit API

#### `GET /api/v1/jobs/{job_id}/audit-events`

用途：查看某个 job 的审计事件。会先检查 job scope，再返回事件。

权限：`audit:read`。

Query：`limit`，默认 100。

#### `GET /api/v1/audit/events`

用途：按当前 scope 查询审计事件，也可按 resource 过滤。适合审计中心、问题排查、合规导出前的数据源。

权限：`audit:read`。

Query：

| 参数 | 说明 |
| --- | --- |
| `resource_type` | 可选，例如 `job`、`action`、`session`、`membership`、`rule_draft` |
| `resource_id` | 可选，具体资源 id |
| `limit` | 1-500，默认 100 |

请求：

```bash
curl -s 'http://127.0.0.1:8010/api/v1/audit/events?resource_type=job&resource_id='$JOB_ID \
  -H "authorization: Bearer $TOKEN"
```

当前已记录的主要事件包括：session 创建/撤销、membership 创建/授权、scan 创建/完成/失败、job/artifact 读取、action 读取/更新、rule draft 创建。

### 4.9 Rule Authoring API

#### `POST /api/v1/rule-authoring/draft-from-text`

用途：把律师审查指南、公司 playbook、谈判原则转成待审核规则草案。生成规则默认 disabled，不会直接写入生产 YAML。

权限：`rule_draft:create`。

请求体：

```json
{
  "guide_text": "合同不得包含无限责任或 unlimited liability。涉及客户数据和训练模型的条款必须升级审核。",
  "rule_scope": "company",
  "scope_id": "acme_playbook",
  "source_name": "2026 procurement guide",
  "max_rules": 12
}
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `guide_text` | 是 | 律师自然语言规则指南 |
| `rule_scope` | 否 | `personal`/`workspace`/`company`/`industry` |
| `scope_id` | 否 | 规则归属 id，默认 `personal` |
| `source_name` | 否 | 来源名称 |
| `max_rules` | 否 | 1-50，默认 12 |

响应：

```json
{
  "ok": true,
  "draft_id": "draft_...",
  "rule_scope": "company",
  "scope_id": "acme_playbook",
  "rules_count": 2,
  "rules": [
    {
      "enabled": false,
      "draft_status": "needs_lawyer_review",
      "rule_id": "draft...",
      "keywords": ["unlimited liability"]
    }
  ],
  "review_checklist": [],
  "warnings": []
}
```

#### `GET /api/v1/rule-authoring/lawyer-ui-recommendations`

用途：返回前端/agent 可读的律师操作界面建议，包括主视图、工作流、server hardening priority。

权限：`rule:read`。

适用场景：还没有正式 UI 时，用该 endpoint 给产品原型、agent 操作台或设计说明生成结构化输入。

### 4.10 Redaction API

#### `POST /api/v1/documents/redact-text`

用途：文本脱敏预览，适合上传前预处理、合同片段共享前遮罩、agent 输出前保护敏感信息。

权限：`document:redact`。

请求体：

```json
{
  "text": "Contact zhangsan@example.com or 13800138000.",
  "mask": "[REDACTED]",
  "detect_names": true
}
```

响应：

```json
{
  "redacted_text": "Contact [REDACTED] or [REDACTED].",
  "findings": [],
  "summary": {"email": 1, "phone": 1}
}
```

## 5. 完整 API Use Case

### Use Case 1：工作区初始化与授权

目标：管理员把律师加入某个 organization/workspace，并赋予角色。

步骤：

1. 使用开发 header 或 `workspace_manager` token 调用 `POST /api/v1/memberships/dev-grant`。
2. 目标律师调用 `POST /api/v1/sessions/dev-login`。
3. 登录返回的 `roles` 应来自 membership，而不是登录请求临时传入的 roles。
4. 前端调用 `GET /api/v1/sessions/me` 初始化用户上下文。

示例：

```bash
curl -s http://127.0.0.1:8010/api/v1/memberships/dev-grant \
  -H 'x-user-id: admin' \
  -H 'x-organization-id: acme_legal' \
  -H 'x-workspace-id: procurement' \
  -H 'content-type: application/json' \
  -d '{"user_id":"lawyer_a","organization_id":"acme_legal","workspace_id":"procurement","roles":["legal_reviewer","rule_author"]}'

TOKEN=$(curl -s http://127.0.0.1:8010/api/v1/sessions/dev-login \
  -H 'content-type: application/json' \
  -d '{"user_id":"lawyer_a","organization_id":"acme_legal","workspace_id":"procurement","roles":["business_submitter"]}' | jq -r .session_token)

curl -s http://127.0.0.1:8010/api/v1/sessions/me \
  -H "authorization: Bearer $TOKEN"
```

预期：`roles` 返回 `legal_reviewer`、`rule_author`，不会使用登录请求里误填的 `business_submitter`。

### Use Case 2：律师粘贴合同文本做 v1.0 审查

目标：快速从文本生成风险、义务、关系、action，并保存报告。

步骤：

1. 律师登录并取得 token。
2. 调用 `POST /api/v1/contract/scan-text`，选择 `rules_v1.0`。
3. 从响应读取 `job_id`、`findings`、`action_anchors`、`report_url`。
4. 调用 `GET /api/v1/jobs/{job_id}/report.md` 下载人类可读报告。
5. 调用 `GET /api/v1/jobs/{job_id}/actions` 进入 action queue。

示例：

```bash
SCAN=$(curl -s http://127.0.0.1:8010/api/v1/contract/scan-text \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"ruleset":"rules_v1.0","semantic_validation":"validate","action_policy":"default","text":"Upon termination, Vendor shall return data within 30 days. This agreement includes unlimited liability."}')

JOB_ID=$(printf '%s' "$SCAN" | jq -r .job_id)

curl -s http://127.0.0.1:8010/api/v1/jobs/$JOB_ID/report.md \
  -H "authorization: Bearer $TOKEN"

curl -s http://127.0.0.1:8010/api/v1/jobs/$JOB_ID/actions \
  -H "authorization: Bearer $TOKEN"
```

### Use Case 3：上传 PDF 并获取批注件

目标：律师上传 PDF 合同，获取 JSON/Markdown/PDF artifact。

步骤：

1. 调用 `POST /api/v1/contract/scan`，上传 PDF。
2. 扫描完成后读取 `report_url`、`markdown_report_url`。
3. 调用 `GET /api/v1/jobs/{job_id}/annotated.pdf` 下载批注 PDF。
4. 如果返回 `404`，说明 PDF layout map 不可用或批注件未生成，可继续使用 JSON/Markdown 报告。

示例：

```bash
SCAN=$(curl -s http://127.0.0.1:8010/api/v1/contract/scan \
  -H "authorization: Bearer $TOKEN" \
  -F 'file=@/path/to/contract.pdf' \
  -F 'ruleset=rules_v1.0' \
  -F 'extraction_backend=auto' \
  -F 'grounding_backend=auto' \
  -F 'action_policy=default')

JOB_ID=$(printf '%s' "$SCAN" | jq -r .job_id)

curl -s -o annotated.pdf http://127.0.0.1:8010/api/v1/jobs/$JOB_ID/annotated.pdf \
  -H "authorization: Bearer $TOKEN"
```

### Use Case 4：异步文件扫描

目标：前端上传文件后立即返回，不阻塞页面。

步骤：

1. 调用 `POST /api/v1/contract/scan-async`。
2. 保存返回的 `job_id`。
3. 每隔几秒调用 `GET /api/v1/jobs/{job_id}`。
4. 当 `status=completed` 时读取 report/action/artifact。

示例：

```bash
QUEUED=$(curl -s http://127.0.0.1:8010/api/v1/contract/scan-async \
  -H "authorization: Bearer $TOKEN" \
  -F 'file=@/path/to/contract.docx' \
  -F 'ruleset=rules_v1.0')

JOB_ID=$(printf '%s' "$QUEUED" | jq -r .job_id)

curl -s http://127.0.0.1:8010/api/v1/jobs/$JOB_ID \
  -H "authorization: Bearer $TOKEN"
```

### Use Case 5：Action Anchor 审查闭环

目标：律师把系统提出的 action 从 proposed 推进到 completed 或 dismissed。

步骤：

1. 扫描使用 `rules_v1.0` 和 `action_policy=default`。
2. 调用 `GET /api/v1/jobs/{job_id}/actions`。
3. 选中某个 `action_id`。
4. 调用 `PATCH /api/v1/jobs/{job_id}/actions/{action_id}` 更新状态。
5. 调用 audit API 留痕检查。

示例：

```bash
ACTION_ID=$(curl -s http://127.0.0.1:8010/api/v1/jobs/$JOB_ID/actions \
  -H "authorization: Bearer $TOKEN" | jq -r '.action_anchors[0].action_id')

curl -s -X PATCH http://127.0.0.1:8010/api/v1/jobs/$JOB_ID/actions/$ACTION_ID \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"status":"completed","decision":"accepted","comment":"Liability cap required before signature."}'

curl -s http://127.0.0.1:8010/api/v1/jobs/$JOB_ID/audit-events \
  -H "authorization: Bearer $TOKEN"
```

### Use Case 6：审计中心查询

目标：审计员或法律主管查看某个资源的操作痕迹。

步骤：

1. 使用 `auditor`、`legal_reviewer`、`workspace_manager` 或 `org_admin` 登录。
2. 调用 `GET /api/v1/audit/events`。
3. 可按 `resource_type` 和 `resource_id` 过滤。

示例：

```bash
curl -s 'http://127.0.0.1:8010/api/v1/audit/events?resource_type=job&resource_id='$JOB_ID'&limit=100' \
  -H "authorization: Bearer $AUDITOR_TOKEN"
```

### Use Case 7：律师指南生成规则草案

目标：把律师经验沉淀为可审核的规则资产。

步骤：

1. `rule_author` 或 `workspace_manager` 登录。
2. 调用 `POST /api/v1/rule-authoring/draft-from-text`。
3. 前端展示生成的 disabled rules、warnings、review checklist。
4. 律师人工审核后，未来再通过独立流程激活到规则库。

示例：

```bash
curl -s http://127.0.0.1:8010/api/v1/rule-authoring/draft-from-text \
  -H "authorization: Bearer $RULE_AUTHOR_TOKEN" \
  -H 'content-type: application/json' \
  -d '{"rule_scope":"company","scope_id":"acme_playbook","source_name":"procurement guide","guide_text":"合同不得包含无限责任或 unlimited liability。服务商处理客户数据时必须有删除和返还义务。"}'
```

### Use Case 8：业务提交人提交合同但不能改 action

目标：业务方能提交材料并看自己的报告，但不能代替律师做法律 action 决策。

步骤：

1. 给业务用户 grant `business_submitter`。
2. 业务用户调用扫描 endpoint。
3. 业务用户可以 `GET /api/v1/jobs/{job_id}` 和 report。
4. 业务用户调用 `PATCH /actions/{action_id}` 时应返回 `403`。

这条 use case 用来验证 RBAC 边界。

### Use Case 9：规则作者只能写规则草案，不能扫描合同

目标：规则作者维护知识资产，但不自动获得合同审查权限。

步骤：

1. 给用户 grant `rule_author`。
2. 用户调用 `POST /api/v1/rule-authoring/draft-from-text`，应成功。
3. 用户调用 `POST /api/v1/contract/scan-text`，应返回 `403`。

这条 use case 已用于验证 membership-derived roles 正常生效。

### Use Case 10：文本脱敏预览

目标：上传前或分享前遮罩邮箱、电话等敏感字段。

步骤：

1. 用户登录并具备 `document:redact`。
2. 调用 `POST /api/v1/documents/redact-text`。
3. 前端展示 `redacted_text` 和命中的 sensitive findings。

示例：

```bash
curl -s http://127.0.0.1:8010/api/v1/documents/redact-text \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"text":"Contact zhangsan@example.com or 13800138000.","detect_names":true}'
```

### Use Case 11：前端获取律师工作台结构建议

目标：为未来 UI 或 agent 操作台生成结构化菜单、页面和 workflow。

步骤：

1. 用户具备 `rule:read`。
2. 调用 `GET /api/v1/rule-authoring/lawyer-ui-recommendations`。
3. 前端/agent 使用返回的 `primary_views`、`workflow`、`server_hardening` 生成产品页面或任务面板。

示例：

```bash
curl -s http://127.0.0.1:8010/api/v1/rule-authoring/lawyer-ui-recommendations \
  -H "authorization: Bearer $TOKEN"
```

### Use Case 12：跨用户/跨工作区隔离验证

目标：确认一个律师不能读另一个律师的 job/report/action。

步骤：

1. `lawyer_a` 扫描合同，得到 `job_id`。
2. `lawyer_b` 使用不同 `user_id` 或不同 workspace 登录。
3. `lawyer_b` 调用 `GET /api/v1/jobs/{job_id}`。
4. 预期返回 `404`，不是 `403`，避免泄露对象存在性。

## 6. 推荐端到端最小流程

### 法律审查员完整闭环

```text
POST /api/v1/memberships/dev-grant
POST /api/v1/sessions/dev-login
GET  /api/v1/sessions/me
GET  /api/v1/rulesets
POST /api/v1/contract/scan-text 或 POST /api/v1/contract/scan
GET  /api/v1/jobs/{job_id}
GET  /api/v1/jobs/{job_id}/report.md
GET  /api/v1/jobs/{job_id}/actions
PATCH /api/v1/jobs/{job_id}/actions/{action_id}
GET  /api/v1/jobs/{job_id}/audit-events
DELETE /api/v1/sessions/current
```

### 规则治理闭环

```text
POST /api/v1/sessions/dev-login
GET  /api/v1/rulesets/{ruleset_id}
POST /api/v1/rule-authoring/draft-from-text
GET  /api/v1/audit/events?resource_type=rule_draft
```

### 审计闭环

```text
POST /api/v1/sessions/dev-login
GET  /api/v1/audit/events
GET  /api/v1/audit/events?resource_type=job&resource_id={job_id}
GET  /api/v1/jobs/{job_id}/audit-events
```

## 7. 当前限制与下一步 API 缺口

当前已实现的是可运行的本地/团队开发后端，不是最终生产权限系统。

已知边界：

- `dev-login` 仍是开发登录，不是真实身份提供方登录。
- Membership 只到 organization/workspace，不到 matter/project/document assignment。
- Rule draft 生成后不会自动持久化到正式规则库，也没有审批激活 API。
- Action 仍保存在 job result JSON 中，不是独立 action table。
- Audit log 是 SQLite 记录，不是不可变审计存储。
- 文件存储是本地 filesystem，不是对象存储。

建议下一批 API：

- Matter/project 创建与成员 assignment API。
- Document registry API，把上传文件先登记为 document，再触发 scan。
- Rule draft persistence、approval、promotion API。
- Action table、assignment、transition policy API。
- Audit export 与 retention policy API。