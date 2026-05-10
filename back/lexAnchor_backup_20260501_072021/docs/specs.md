下面是 **LexAnchor（锚点）· 合同版 v0.1 Rule 规范定义**。
目标是给工程师直接实现，不讲玄学。

---

# LexAnchor（锚点）· 合同版 v0.1 规则规范

## 0. v0.1 定位

**LexAnchor v0.1 是一个 合同红旗条款初筛工具。**

它不做最终法律判断，只做四件事：

1. **Text Anchor**：找出明确出现的风险文本。
2. **Missing Anchor**：发现关键条款缺失。
3. **Risk Anchor**：给每个命中项绑定风险等级。
4. **Context Anchor**：识别合同适用法律、管辖、合同类型等上下文。

v0.1 不启用完整 Semantic Anchor。
现有 `requires_llm: true` 的规则只作为 **候选项** 标记，不进入最终高危结论，除非后续 v0.2 接入 LLM Validator。

你当前的 9 条规则可以作为 v0.1 的初始规则资产，其中包含 Text、Missing、Semantic 候选三类。

---

# 1. v0.1 业务逻辑

## 1.1 输入

系统接收一份合同文件：

* PDF
* DOCX
* TXT
* Markdown

v0.1 推荐优先支持：

* PDF
* TXT

---

## 1.2 输出

系统稳定输出三类结果：

### A. JSON 审查报告

文件名建议：

```text
review_report.json
```

内容包括：

* 文档信息
* 上下文信息
* 风险摘要
* Text Anchors
* Missing Anchors
* Semantic Candidates
* 渲染信息
* 免责声明

---

### B. 高亮 PDF

文件名建议：

```text
annotated_contract.pdf
```

渲染逻辑：

* Text Anchor：在原文位置高亮。
* Missing Anchor：放在首页摘要区。
* Context Anchor：放在报告摘要区。
* Semantic Candidate：v0.1 默认不高亮，可在报告中列为“待人工复核候选”。

---

### C. Markdown / HTML 报告

文件名建议：

```text
review_report.md
```

用于 Agent 给用户直接展示。

---

# 2. v0.1 Anchor 类型

## 2.1 Text Anchor

用于明确文本命中。

适用规则类型：

```yaml
type: keyword
type: pattern
```

典型规则：

* 无限责任
* 单方修改
* 自动续约

渲染方式：

```json
{
  "anchor_type": "text",
  "render_strategy": "highlight_text"
}
```

---

## 2.2 Missing Anchor

用于关键条款缺失。

适用规则类型：

```yaml
type: missing
```

典型规则：

* 缺少终止条款
* 缺少数据删除 / 返还条款
* 缺少适用法律 / 管辖条款

渲染方式：

```json
{
  "anchor_type": "missing",
  "anchor_scope": "document",
  "render_strategy": "summary_card"
}
```

注意：

**Missing Anchor 没有原文 bbox。**

它不能伪造位置，应该放在首页审查摘要区。

---

## 2.3 Risk Anchor

Risk Anchor 不是独立规则，而是每条规则的风险解释层。

每个 finding 都必须包含：

```json
{
  "risk": {
    "severity": "critical",
    "risk_type": "financial_exposure",
    "confidence": 0.92,
    "human_review_needed": true
  }
}
```

v0.1 支持四级：

```text
critical
high
medium
low
```

---

## 2.4 Context Anchor

Context Anchor 用于识别合同的解释坐标系。

v0.1 只做识别和展示，不做复杂法域推理。

需要提取：

```json
{
  "context": {
    "contract_type": "saas_vendor",
    "governing_law": "New York",
    "jurisdiction": "New York courts",
    "language": "en",
    "detected_parties": []
  }
}
```

v0.1 规则：

* 如果检测到适用法律 / 管辖条款，提取内容。
* 如果未检测到，触发 `contract.missing_governing_law`。
* 不输出“该条款在某法域违法”这类结论。

---

## 2.5 Semantic Candidate

v0.1 可以保留 semantic 类型规则，但不做最终判断。

例如：

* 单方免责 / 单方赔偿不对等
* 知识产权归属异常
* 审计权过宽

处理方式：

```json
{
  "anchor_type": "semantic_candidate",
  "status": "needs_human_or_llm_validation",
  "included_in_summary_score": false,
  "render_strategy": "report_only"
}
```

---

# 3. 规则 YAML 规范

## 3.1 顶层结构

规则文件统一命名：

```text
rules_v0.1.yaml
```

结构：

```yaml
version: "0.1"
domain: "contract"
contract_scope: "saas_vendor"
rules:
  - rule_id: contract.unlimited_liability
    ...
```

---

# 4. 单条规则完整字段

## 4.1 必填字段

```yaml
rule_id: contract.unlimited_liability
name: 无限责任条款检测
category: liability
severity: critical
type: keyword
anchor_type: text
description: >
  条款中未设置责任上限，可能导致责任暴露不可控。
why_it_matters: >
  无限责任可能导致企业承担不可预估的商业及财务损失风险。
recommendation: >
  建议增加责任上限。
requires_llm: false
escalation: true
```

---

## 4.2 可选字段

```yaml
risk_type: financial_exposure
confidence_base: 0.9
enabled: true
jurisdiction_tags:
  - general
  - us
  - cn
negative_filter:
  enabled: true
  window_chars: 40
  terms:
    - "不适用"
    - "不构成"
    - "不承担"
    - "not apply"
    - "shall not"
render:
  color: red
  style: highlight
```

---

# 5. 规则类型定义

## 5.1 keyword 规则

用于字符串命中。

```yaml
- rule_id: contract.unlimited_liability
  name: 无限责任条款检测
  category: liability
  severity: critical
  type: keyword
  anchor_type: text
  trigger:
    any:
      - "无限责任"
      - "不设任何赔偿上限"
      - "without limitation of liability"
      - "unlimited liability"
      - "承担全部损失"
      - "承担全部赔偿责任"
  description: >
    条款中未设置责任上限，可能导致责任暴露不可控。
  why_it_matters: >
    无限责任可能导致企业承担不可预估的商业及财务损失风险。
  recommendation: >
    建议增加责任上限，例如合同金额的12个月费用，并明确排除间接损失。
  risk_type: financial_exposure
  requires_llm: false
  escalation: true
```

执行逻辑：

```text
如果 trigger.any 中任一文本出现在文档段落中，则命中。
```

---

## 5.2 pattern 规则

用于正则匹配。

```yaml
- rule_id: contract.daily_penalty
  name: 高额日违约金检测
  category: liability
  severity: high
  type: pattern
  anchor_type: text
  trigger:
    regex:
      - "每日.*合同总额.*[0-9]+%"
      - "per day.*total.*[0-9]+%"
  description: >
    条款可能设置过高的日违约金。
  why_it_matters: >
    高额日违约金可能造成违约成本异常放大。
  recommendation: >
    建议将违约金比例调整至合理范围，并设置上限。
  requires_llm: false
  escalation: true
```

执行逻辑：

```text
对每个段落执行 regex 匹配，命中后生成 Text Anchor。
```

---

## 5.3 missing 规则

用于检测关键条款缺失。

```yaml
- rule_id: contract.missing_termination
  name: 缺少终止条款
  category: structure
  severity: critical
  type: missing
  anchor_type: missing
  trigger:
    required_any:
      - "解除本合同"
      - "合同终止"
      - "终止本协议"
      - "termination"
      - "终止权"
  description: >
    全篇未发现合同解除或终止相关条款。
  why_it_matters: >
    若合作僵局或对方违约，缺少退出机制可能导致持续成本消耗。
  recommendation: >
    补充单方解除权、违约解除权，并建议争取提前通知的无因解除权。
  requires_llm: false
  escalation: true
```

执行逻辑：

```text
如果 required_any 中任一文本在全文出现，则通过。
如果全部未出现，则生成 Missing Anchor。
```

---

## 5.4 semantic 规则

v0.1 只生成候选，不做最终风险结论。

```yaml
- rule_id: contract.ip_ownership_anomaly
  name: 知识产权归属异常
  category: intellectual_property
  severity: high
  type: semantic
  anchor_type: semantic_candidate
  trigger:
    any:
      - "知识产权"
      - "所有权"
      - "交付物归"
      - "intellectual property"
      - "IP rights"
      - "work product"
  description: >
    检测到知识产权相关条款，需进一步判断其归属是否异常。
  why_it_matters: >
    可能导致企业出钱开发却丧失核心业务资产所有权。
  recommendation: >
    建议人工复核定制开发成果、背景知识产权和许可范围。
  requires_llm: true
  escalation: true
```

v0.1 执行逻辑：

```text
命中 trigger 后，仅输出 semantic_candidate。
不计入 final risk score。
不在 PDF 主文高亮。
可在报告中显示为“待复核候选”。
```

v0.2 才启用：

```text
LLM Validator → is_valid=true → 转为 Semantic Anchor
```

---

# 6. v0.1 推荐规则清单

v0.1 建议正式启用 6 条规则：

## Text Anchor 规则

1. `contract.unlimited_liability`
2. `contract.unilateral_change`
3. `contract.auto_renewal`

## Missing Anchor 规则

4. `contract.missing_termination`
5. `contract.missing_data_deletion`
6. `contract.missing_governing_law`

## Semantic Candidate 规则

7. `contract.indemnity_imbalance`
8. `contract.ip_ownership_anomaly`
9. `contract.overbroad_audit_rights`

说明：

第 7–9 条在 v0.1 只做候选提示，不作为最终风险结论。

---

# 7. v0.1 数据逻辑

## 7.1 文档解析输出

Extractor 输出统一格式：

```json
{
  "document_id": "doc_001",
  "file_name": "contract.pdf",
  "pages": [
    {
      "page_num": 1,
      "blocks": [
        {
          "block_id": "p1_b1",
          "text": "This Agreement shall automatically renew...",
          "bbox": [100.0, 200.0, 450.0, 230.0],
          "line_bboxes": []
        }
      ]
    }
  ],
  "full_text": "..."
}
```

---

## 7.2 Rule Engine 输入

```json
{
  "document_id": "doc_001",
  "full_text": "...",
  "blocks": [
    {
      "block_id": "p1_b1",
      "page_num": 1,
      "text": "...",
      "bbox": [100, 200, 450, 230]
    }
  ],
  "ruleset": "rules_v0.1.yaml"
}
```

---

## 7.3 Rule Engine 输出

```json
{
  "text_anchors": [],
  "missing_anchors": [],
  "semantic_candidates": [],
  "context_anchors": []
}
```

---

# 8. Finding 标准结构

所有命中项统一称为 `finding`。

```json
{
  "finding_id": "F-0001",
  "rule_id": "contract.unlimited_liability",
  "rule_name": "无限责任条款检测",
  "category": "liability",
  "anchor_type": "text",
  "anchor_scope": "paragraph",
  "status": "confirmed",
  "severity": "critical",
  "risk": {
    "risk_type": "financial_exposure",
    "severity": "critical",
    "confidence": 0.92,
    "human_review_needed": true
  },
  "evidence": {
    "matched_text": "Vendor shall indemnify Customer without limitation of liability.",
    "trigger": "without limitation of liability",
    "page_num": 4,
    "block_id": "p4_b12",
    "bbox": [100.5, 200.0, 450.2, 215.0]
  },
  "description": "条款中未设置责任上限，可能导致责任暴露不可控。",
  "why_it_matters": "无限责任可能导致企业承担不可预估的商业及财务损失风险。",
  "recommendation": "建议增加责任上限。",
  "render": {
    "strategy": "highlight_text",
    "color": "red"
  }
}
```

---

# 9. Missing Finding 标准结构

```json
{
  "finding_id": "M-0001",
  "rule_id": "contract.missing_data_deletion",
  "rule_name": "缺少数据删除 / 返还条款",
  "category": "structure",
  "anchor_type": "missing",
  "anchor_scope": "document",
  "status": "confirmed",
  "severity": "high",
  "risk": {
    "risk_type": "data_security_exposure",
    "severity": "high",
    "confidence": 0.95,
    "human_review_needed": true
  },
  "evidence": {
    "matched_text": null,
    "trigger": null,
    "page_num": null,
    "block_id": null,
    "bbox": null
  },
  "description": "未发现合同终止后关于业务/用户数据如何处理的明确约定。",
  "why_it_matters": "未规定数据销毁义务可能引发商业机密泄露及数据合规风险。",
  "recommendation": "补充合同终止后的数据返还、删除和销毁证明条款。",
  "render": {
    "strategy": "summary_card",
    "color": "orange"
  }
}
```

---

# 10. Semantic Candidate 标准结构

```json
{
  "finding_id": "S-0001",
  "rule_id": "contract.ip_ownership_anomaly",
  "rule_name": "知识产权归属异常",
  "category": "intellectual_property",
  "anchor_type": "semantic_candidate",
  "anchor_scope": "paragraph",
  "status": "needs_validation",
  "severity": "high",
  "included_in_summary_score": false,
  "risk": {
    "risk_type": "ip_ownership_exposure",
    "severity": "high",
    "confidence": 0.5,
    "human_review_needed": true
  },
  "evidence": {
    "matched_text": "All intellectual property rights in the work product...",
    "trigger": "intellectual property",
    "page_num": 5,
    "block_id": "p5_b3",
    "bbox": [100, 240, 460, 280]
  },
  "description": "检测到知识产权相关条款，需进一步判断其归属是否异常。",
  "recommendation": "建议人工复核定制开发成果、背景知识产权和许可范围。",
  "render": {
    "strategy": "report_only",
    "color": "gray"
  }
}
```

---

# 11. Context Anchor 结构

Context Anchor 独立于 finding，但可以影响报告摘要。

```json
{
  "context_id": "C-0001",
  "anchor_type": "context",
  "context_type": "governing_law",
  "value": "State of New York",
  "confidence": 0.87,
  "evidence": {
    "matched_text": "This Agreement shall be governed by the laws of the State of New York.",
    "page_num": 9,
    "block_id": "p9_b2",
    "bbox": [100, 300, 470, 330]
  },
  "render": {
    "strategy": "context_summary",
    "color": "blue"
  }
}
```

v0.1 Context 类型：

```text
governing_law
jurisdiction
contract_type
language
party_names
```

---

# 12. 否定词过滤规范

## 12.1 目的

减少 keyword 规则误报。

例如：

```text
本条款不适用于无限责任的情况。
```

不能直接作为无限责任风险。

---

## 12.2 v0.1 策略

只做轻量级窗口过滤。

```yaml
negative_filter:
  enabled: true
  window_chars: 40
  terms:
    - "不适用"
    - "不构成"
    - "不承担"
    - "不应视为"
    - "not apply"
    - "does not apply"
    - "shall not"
    - "not constitute"
```

---

## 12.3 输出逻辑

如果命中 trigger，但附近出现否定词：

```json
{
  "status": "suppressed",
  "suppressed_reason": "negation_filter",
  "included_in_summary_score": false
}
```

v0.1 默认：

* 不高亮
* 不计入风险摘要
* 可记录在 debug 报告中

---

# 13. 风险摘要计算规则

只统计：

```text
status = confirmed
included_in_summary_score != false
```

不统计：

```text
semantic_candidate
suppressed
debug_only
```

摘要结构：

```json
{
  "summary": {
    "critical": 1,
    "high": 2,
    "medium": 0,
    "low": 0,
    "missing": 2,
    "semantic_candidates": 3,
    "suppressed": 1
  }
}
```

---

# 14. v0.1 完整输出 JSON

```json
{
  "version": "0.1",
  "product": "LexAnchor",
  "mode": "contract_scan",
  "document_info": {
    "document_id": "doc_001",
    "file_name": "cloud_service_agreement.pdf",
    "file_type": "pdf",
    "total_pages": 12,
    "language": "en"
  },
  "context": {
    "contract_type": "saas_vendor",
    "governing_law": "State of New York",
    "jurisdiction": "New York courts",
    "party_names": ["Customer", "Vendor"]
  },
  "summary": {
    "critical": 1,
    "high": 2,
    "medium": 0,
    "low": 0,
    "missing": 2,
    "semantic_candidates": 3,
    "suppressed": 0
  },
  "findings": [],
  "missing_anchors": [],
  "semantic_candidates": [],
  "context_anchors": [],
  "artifacts": {
    "annotated_pdf_url": "/artifacts/doc_001/annotated_contract.pdf",
    "json_report_url": "/artifacts/doc_001/review_report.json",
    "markdown_report_url": "/artifacts/doc_001/review_report.md"
  },
  "disclaimer": "本结果为规则驱动的合同初筛与风险定位，不构成最终法律意见。"
}
```

---

# 15. 服务器版架构

## 15.1 服务器职责

服务器只做专业能力：

```text
文件接收
文档解析
规则加载
规则扫描
上下文提取
PDF 渲染
报告生成
结果存储
```

服务器不负责：

```text
用户对话
复杂业务解释
多轮聊天
Agent 记忆
```

---

## 15.2 服务模块

```text
lexanchor-server/
├── api/
│   ├── routes_scan.py
│   ├── routes_rules.py
│   └── routes_artifacts.py
├── core/
│   ├── extractor.py
│   ├── rule_engine.py
│   ├── context_detector.py
│   ├── risk_mapper.py
│   ├── renderer.py
│   └── report_generator.py
├── rules/
│   └── rules_v0.1.yaml
├── schemas/
│   ├── rule_schema.py
│   ├── finding_schema.py
│   └── api_schema.py
└── storage/
```

---

# 16. 服务器 API 设计

## 16.1 上传并扫描合同

```http
POST /api/v1/contract/scan
Content-Type: multipart/form-data
```

参数：

```text
file: contract.pdf
ruleset: rules_v0.1
render_pdf: true
return_markdown: true
```

响应：

```json
{
  "job_id": "job_123",
  "status": "completed",
  "result": {
    "summary": {
      "critical": 1,
      "high": 2,
      "missing": 1
    },
    "report_url": "/api/v1/jobs/job_123/report",
    "annotated_pdf_url": "/api/v1/jobs/job_123/artifacts/annotated.pdf"
  }
}
```

---

## 16.2 异步扫描

适合大文件。

```http
POST /api/v1/contract/scan-async
```

响应：

```json
{
  "job_id": "job_123",
  "status": "queued"
}
```

查询：

```http
GET /api/v1/jobs/{job_id}
```

响应：

```json
{
  "job_id": "job_123",
  "status": "completed",
  "progress": 100
}
```

---

## 16.3 获取 JSON 报告

```http
GET /api/v1/jobs/{job_id}/report.json
```

---

## 16.4 获取 Markdown 报告

```http
GET /api/v1/jobs/{job_id}/report.md
```

---

## 16.5 获取高亮 PDF

```http
GET /api/v1/jobs/{job_id}/annotated.pdf
```

---

## 16.6 规则集检查

```http
GET /api/v1/rulesets/rules_v0.1
```

返回：

```json
{
  "ruleset": "rules_v0.1",
  "version": "0.1",
  "rule_count": 9,
  "enabled_anchor_types": [
    "text",
    "missing",
    "risk",
    "context"
  ]
}
```

---

## 16.7 纯文本扫描 API

给 Agent 或测试用。

```http
POST /api/v1/contract/scan-text
Content-Type: application/json
```

请求：

```json
{
  "text": "This agreement shall automatically renew...",
  "ruleset": "rules_v0.1",
  "contract_type": "saas_vendor"
}
```

响应：

```json
{
  "summary": {
    "critical": 0,
    "high": 1,
    "missing": 2
  },
  "findings": []
}
```

---

# 17. Agent 调用 API 设计

Agent 不直接执行规则，不直接解析 PDF。
Agent 只负责：

1. 接收用户请求。
2. 上传文件给服务器。
3. 等待结果。
4. 解释结果。
5. 返回报告和 PDF 链接。

---

## 17.1 Agent Tool 定义

工具名：

```text
lexanchor_contract_scan
```

工具描述：

```text
对 SaaS/Vendor 合同进行红旗条款初筛，返回结构化风险报告和高亮 PDF。
```

输入 schema：

```json
{
  "file_path": "string",
  "ruleset": "rules_v0.1",
  "render_pdf": true,
  "return_markdown": true
}
```

输出 schema：

```json
{
  "job_id": "string",
  "summary": {
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0,
    "missing": 0,
    "semantic_candidates": 0
  },
  "top_findings": [
    {
      "rule_id": "string",
      "severity": "string",
      "title": "string",
      "page_num": 1,
      "recommendation": "string"
    }
  ],
  "artifacts": {
    "annotated_pdf_url": "string",
    "json_report_url": "string",
    "markdown_report_url": "string"
  }
}
```

---

## 17.2 Agent 调用流程

```text
用户上传合同
   ↓
Agent 判断意图：合同初筛
   ↓
Agent 调用 lexanchor_contract_scan
   ↓
服务器返回 JSON + PDF
   ↓
Agent 总结高风险项
   ↓
Agent 提醒：不是最终法律意见
   ↓
Agent 提供报告链接
```

---

## 17.3 Agent 回复模板

```text
已完成 LexAnchor 合同初筛。

本次共发现：
- Critical：{critical_count}
- High：{high_count}
- Missing：{missing_count}
- Semantic Candidates：{semantic_count}

重点风险：
1. {finding_1}
2. {finding_2}

高亮版 PDF：{annotated_pdf_url}
完整 JSON 报告：{json_report_url}

说明：本结果为规则驱动的初筛与风险定位，不构成最终法律意见。
```

---

# 18. 工程实现优先级

## P0 必须实现

```text
rules_v0.1.yaml loader
keyword matcher
missing checker
context detector
risk mapper
JSON report
scan-text API
scan-file API
```

---

## P1 应实现

```text
PDF bbox extraction
PDF highlight renderer
Markdown report
negative filter
async job
```

---

## P2 暂缓

```text
LLM Validator
Semantic Anchor confirmed mode
risk graph
redline suggestions
multi-jurisdiction adjustment
```

---

# 19. 验收标准

## 19.1 Rule Engine

Text Anchor：

```text
包含“不设任何赔偿上限” → 必须命中 contract.unlimited_liability
```

Missing Anchor：

```text
全文无“终止 / termination” → 必须生成 contract.missing_termination
```

Negative Filter：

```text
“本条不适用于无限责任” → 不应进入 confirmed finding
```

Context Anchor：

```text
“This Agreement shall be governed by the laws of New York”
→ 提取 governing_law = New York
```

---

## 19.2 API

必须通过：

```text
POST /api/v1/contract/scan-text
POST /api/v1/contract/scan
GET /api/v1/jobs/{job_id}/report.json
GET /api/v1/jobs/{job_id}/annotated.pdf
```

---

# 20. 工作方向

> v0.1 不做“AI 法律判断”。
> v0.1 做的是：加载规则 → 扫描合同 → 生成 Text / Missing / Context Anchors → 叠加 Risk 信息 → 输出 JSON 和高亮 PDF。
> Agent 只调用服务器 API，不直接运行审查逻辑。
