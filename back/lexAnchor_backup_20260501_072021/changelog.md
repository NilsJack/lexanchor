# LexAnchor Changelog

## 2026-05-01 - v0.1.1 progress note

### Status

- v0.1.1 is still in progress. We are prioritizing forward implementation speed and have not performed final test acceptance.
- Current validation is limited to developer checks, unit tests, and HTTP smoke checks. These checks are useful for progress tracking, but they do not equal product, security, legal-domain, or user acceptance testing.
- The current access isolation is a lightweight request-scope mechanism for development. Full workgroup permission settings and RBAC are recorded as future design work, not implemented in this iteration.

### Implemented Progress

- Server-side LexAnchor framework has FastAPI endpoints for text/file scan, ruleset inspection, redaction preview, reports, hosted API documentation, and job/artifact retrieval.
- v0.1 anchor scope is Text Anchor, Missing Anchor, Risk Anchor, and Context Anchor.
- v0.1.1 adds the PDF artifact loop: PDF layout extraction, JSON/Markdown report URLs, annotated PDF rendering, and scoped artifact access.
- Docling and LangExtract are integrated as optional extraction/grounding capabilities with local fallbacks.

### Rule Asset Reality

- The current `rules_v0.1` ruleset is only a minimal baseline of 9 general contract-review rules.
- These rules are enough to prove the server pipeline, but they are not enough to represent the real professional experience of a legal team.
- Rule content is the core legal knowledge asset of LexAnchor. It should be treated as lawyer experience, company playbook knowledge, and review methodology, not just static configuration.

### Rule Roadmap

The rule system should grow in staged iterations:

1. Rule management tools
   - Add APIs and tools for creating, editing, validating, importing, exporting, versioning, and disabling rules.
   - Add rule preview/testing against sample contracts before a rule is activated.
   - Track rule author, reviewer, version, effective date, and audit history.
   - Support personal, team, workspace, and company rule scopes so lawyers can preserve their own review methods without forcing every rule into a global baseline.

2. Anchor-specific rule expansion
   - Add more dedicated rules for each anchor type instead of relying on the current general-purpose baseline.
   - Text Anchor rules should cover more explicit clause language and phrase variants.
   - Missing Anchor rules should cover required clause absence by contract type, industry, jurisdiction, and transaction scenario.
   - Risk Anchor rules should cover risk taxonomy, severity policy, fallback wording, negotiation posture, and review escalation hints.
   - Context Anchor rules should cover document type, party role, governing law signals, industry context, deal size, language, and workflow scenario.

3. Domain and industry normative rule packs
   - Build vertical rule packs for specific domains and industries, including maritime/shipping where needed, construction, SaaS, procurement, employment, privacy, finance, and cross-border trade.
   - Each pack should contain baseline legal norms, common clause patterns, unacceptable positions, negotiable positions, and required review checkpoints.
   - These packs should be attachable by organization, workspace, matter, contract type, and industry.

4. Company-rule extraction
   - Add tools to extract company-specific rules from existing templates, playbooks, reviewed contracts, negotiation comments, redline history, and legal memos.
   - Support human lawyer approval before extracted rules become active.
   - Separate extracted company policy from generic legal-domain rules.

5. Rule governance
   - Add rule quality checks: duplicate detection, conflict detection, overly broad trigger detection, missing recommendation detection, and test coverage status.
   - Add rule lifecycle states: draft, reviewed, active, deprecated, archived.
   - Add rule impact reports showing which findings, documents, and teams are affected by a rule change.

6. Personalized rule assets
   - Personalized rules are a core expression of lawyer capability, not a secondary settings feature.
   - Future versions should allow a lawyer to add, delete, edit, test, and carry forward their own rule library.
   - Rule visibility should be explicit: private personal rules, team-shared rules, workspace rules, company playbook rules, and platform baseline rules.
   - Personal rules should be exportable/importable so legal professionals can preserve accumulated expertise across matters and organizations when permitted.
   - Company or team promotion should require review and approval, because a personal rule may reflect individual judgment rather than company policy.

### Iteration Placement

- v0.1.1: keep the minimal 9-rule baseline and finish the artifact/report/server loop.
- v0.2: add Semantic Anchors and Escalation Anchors, then begin richer anchor-specific rules.
- v0.3: add Obligation Anchors and Relation Anchors, then expand domain/industry rule packs.
- v0.4+: add rule management APIs, company-rule extraction, approval workflow, and rule governance tools.
- v1.0: make rules a first-class company legal knowledge system with RBAC, audit logs, versioning, playbooks, and review workflow integration.

## 2026-05-01 - v0.2 progress note

### Anchor Capability Switch

- Added explicit anchor capability profiles so each version has its own allowed anchor-finding abilities.
- `v0.1` and `v0.1.1` are limited to Text, Missing, Risk, and Context Anchors.
- `v0.2` adds Semantic Candidate, Semantic, and Escalation Anchors.
- Requests may pass `anchor_profile` and `enabled_anchors` to narrow the active anchors, but the server will not enable anchors outside the selected profile.
- This prevents v0.1 scans from accidentally using v0.2 Semantic or Escalation behavior even when semantic-style rules exist in the rule file.

### v0.2 Implementation Progress

- Added an inherited `rules_v0.2` ruleset that extends `rules_v0.1` and adds initial semantic review rules.
- Added local Semantic Anchor validation as a deterministic first v0.2 validator before external LLM routing is connected.
- Added explicit Escalation Anchor output and review-queue metadata.
- Validation remains developer-level only; no final product acceptance has been performed.

### Baseline Test Rule Pack

- Expanded `rules_v0.2` with a basic semantic test-rule pack before moving into v0.3.
- The pack is intended for pipeline, anchor-profile, and escalation-route testing. It is not a complete legal rule library and has not received final lawyer-domain acceptance.
- Added baseline coverage for customer data/model training, broad customer-content licenses, residual confidentiality exceptions, subprocessors without notice, unilateral suspension, unilateral pricing changes, exclusive remedy limits, SLA discretion, and export/sanctions compliance responsibility shifts.
- Added tests to verify that `rules_v0.2` inherits `rules_v0.1`, exposes Semantic/Escalation capabilities, and triggers the new baseline Semantic Candidate rules.
- With these basic rules in place, the next implementation line can move to v0.3: Obligation Anchors and Relation Anchors.

## 2026-05-01 - v0.3 progress note

### Obligation and Relation Anchors

- Added `rules_v0.3`, inherited from `rules_v0.2`.
- Added baseline Obligation Anchor rules for payment timing, notice period, data return/deletion, and security incident notice duties.
- Added baseline Relation Anchor rules for termination -> data return/deletion dependency and service level -> service credit dependency.
- Extended the scan engine to support `type: obligation` and `type: relation` rules under the v0.3 anchor capability profile.
- Added explicit `obligation_anchors` and `relation_anchors` result sections and summary counts.
- Markdown reports now include obligation and relation anchor counts and sections.
- Validation remains developer-level only; these are basic test rules for v0.3 pipeline progress, not final lawyer-domain acceptance.

## 2026-05-01 - v1.0 progress note

### Action Anchors

- Added `rules_v1.0`, inherited from `rules_v0.3`, to activate the v1.0 anchor capability profile.
- Added Action Anchor generation as a post-scan workflow bridge.
- Action Anchors convert findings, Escalation Anchors, Obligation Anchors, and Relation Anchors into proposed legal-review actions.
- Added `action_anchors`, `action_queue`, and `action_policy` output sections.
- Each Action Anchor includes priority, owner role, action type, due policy, source anchor metadata, status, and recommendation.
- Added `action_policy=default|disabled` request control.
- Markdown reports now include Action Anchor counts and sections.
- This is a first runnable v1.0 Action Anchor layer, not a full production workflow engine, task system, RBAC implementation, or durable queue.

### Minimal runtime loop

- Added SQLite-backed audit events for scan lifecycle, job/artifact reads, action reads, and action status updates.
- Added scoped audit event query endpoint: `GET /api/v1/audit/events`.
- Added job-scoped audit event query endpoint: `GET /api/v1/jobs/{job_id}/audit-events`.
- Added scoped action list endpoint: `GET /api/v1/jobs/{job_id}/actions`.
- Added scoped action status update endpoint: `PATCH /api/v1/jobs/{job_id}/actions/{action_id}`.
- Action status updates are persisted into the job result JSON and mirrored into action queue items when present.
- The current action workflow is intentionally minimal: `proposed`, `accepted`, `in_progress`, `completed`, and `dismissed`.
- This gives v1.0 a runnable scan -> proposed action -> status update -> audit trail loop, while full task tables, reviewer assignment, immutable audit retention, RBAC, and durable queues remain future work.

### Rule authoring automation and lawyer UI planning

- Added deterministic rule draft generation from lawyer guidance text: `POST /api/v1/rule-authoring/draft-from-text`.
- Generated rules are disabled by default and marked `draft_status: needs_lawyer_review`.
- Rule draft creation writes a scoped `rule_draft.created` audit event.
- Added structured lawyer operation UI recommendations: `GET /api/v1/rule-authoring/lawyer-ui-recommendations`.
- UI recommendations cover review workspace, action queue, rule authoring workspace, audit center, workflow steps, and server hardening priorities.
- This automates rule drafting, not final rule approval or activation; production rule governance remains future work.

### Session-control hardening

- Added SQLite-backed server sessions with token hashing, expiry, and revocation.
- Added `POST /api/v1/sessions/dev-login`, `GET /api/v1/sessions/me`, and `DELETE /api/v1/sessions/current`.
- Request scope resolution now prefers `Authorization: Bearer ...` or `X-LexAnchor-Session` before falling back to development scope headers.
- Session creation and revocation write audit events.
- This is the first session-control layer, not complete production authentication or RBAC.
