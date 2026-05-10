from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app.config import get_settings
from app.services.access_control import RequestScope, assert_job_access
from app.services.action_anchor import ActionAnchorService
from app.services.anchor_engine import AnchorEngine
from app.services.audit_log import AuditLogStore
from app.services.context_detector import ContextDetector
from app.services.document_service import DocumentService
from app.services.escalation_policy import EscalationPolicyService
from app.services.job_store import JobStore
from app.services.langextract_grounding import LangExtractGroundingService
from app.services.pdf_renderer import PdfRenderer
from app.services.rule_authoring import RuleDraftGenerator
from app.services.rule_loader import RuleLoader
from app.services.semantic_validator import SemanticValidatorService


class AnchorEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        settings = get_settings()
        self.rule_loader = RuleLoader(settings.rules_dir)
        self.engine = AnchorEngine(self.rule_loader, ContextDetector())

    def test_keyword_anchor_hits_unlimited_liability(self) -> None:
        result = self.engine.scan_text(
            "This agreement includes unlimited liability and shall automatically renew.",
            ruleset="rules_v0.1",
        )
        rule_ids = {finding["rule_id"] for finding in result["findings"]}
        self.assertIn("contract.unlimited_liability", rule_ids)
        self.assertIn("contract.auto_renewal", rule_ids)
        self.assertGreaterEqual(result["summary"]["escalations"], 2)

    def test_missing_anchor_for_absent_termination(self) -> None:
        result = self.engine.scan_text("This agreement has a payment term only.", ruleset="rules_v0.1")
        rule_ids = {finding["rule_id"] for finding in result["missing_anchors"]}
        self.assertIn("contract.missing_termination", rule_ids)
        self.assertIn("contract.missing_governing_law", rule_ids)

    def test_negation_filter_suppresses_keyword(self) -> None:
        result = self.engine.scan_text("This clause does not apply to unlimited liability.", ruleset="rules_v0.1")
        suppressed_rule_ids = {finding["rule_id"] for finding in result["suppressed_findings"]}
        confirmed_rule_ids = {finding["rule_id"] for finding in result["findings"]}
        self.assertIn("contract.unlimited_liability", suppressed_rule_ids)
        self.assertNotIn("contract.unlimited_liability", confirmed_rule_ids)

    def test_v0_1_profile_disables_semantic_rules(self) -> None:
        result = self.engine.scan_text("All intellectual property in the work product belongs to Vendor.", ruleset="rules_v0.1")
        self.assertEqual(result["anchor_capabilities"]["profile"], "v0.1")
        self.assertNotIn("semantic", result["anchor_capabilities"]["enabled_anchors"])
        self.assertEqual(result["semantic_candidates"], [])

    def test_v0_2_profile_enables_semantic_candidates(self) -> None:
        result = self.engine.scan_text("All intellectual property in the work product belongs to Vendor.", ruleset="rules_v0.2")
        candidate_rule_ids = {finding["rule_id"] for finding in result["semantic_candidates"]}
        self.assertEqual(result["anchor_capabilities"]["profile"], "v0.2")
        self.assertIn("semantic", result["anchor_capabilities"]["enabled_anchors"])
        self.assertIn("contract.ip_ownership_anomaly", candidate_rule_ids)
        self.assertEqual(result["summary"]["semantic_candidates"], 2)

    def test_v0_2_ruleset_extends_v0_1_with_baseline_semantic_rules(self) -> None:
        description = self.rule_loader.describe_ruleset("rules_v0.2")
        rule_ids = {rule["rule_id"] for rule in description["rules"]}
        self.assertEqual(description["extends"], "rules_v0.1")
        self.assertGreaterEqual(description["rule_count"], 19)
        self.assertIn("semantic", description["enabled_anchor_types"])
        self.assertIn("escalation", description["enabled_anchor_types"])
        self.assertIn("contract.ai_training_data_use", rule_ids)
        self.assertIn("contract.customer_content_broad_license", rule_ids)
        self.assertIn("contract.confidentiality_residual_knowledge", rule_ids)
        self.assertIn("contract.subprocessor_without_notice", rule_ids)
        self.assertIn("contract.unilateral_suspension_without_cure", rule_ids)
        self.assertIn("contract.exclusive_remedy_limitation", rule_ids)

    def test_v0_2_baseline_rules_trigger_semantic_candidates(self) -> None:
        text = (
            "Vendor may use Customer Data to improve services and train models. "
            "Vendor may appoint subprocessors without notice. "
            "Customer's sole and exclusive remedy is service credit."
        )
        result = self.engine.scan_text(text, ruleset="rules_v0.2")
        candidate_rule_ids = {finding["rule_id"] for finding in result["semantic_candidates"]}
        self.assertIn("contract.ai_training_data_use", candidate_rule_ids)
        self.assertIn("contract.customer_content_broad_license", candidate_rule_ids)
        self.assertIn("contract.subprocessor_without_notice", candidate_rule_ids)
        self.assertIn("contract.exclusive_remedy_limitation", candidate_rule_ids)

    def test_v0_3_ruleset_adds_obligation_and_relation_capabilities(self) -> None:
        description = self.rule_loader.describe_ruleset("rules_v0.3")
        rule_ids = {rule["rule_id"] for rule in description["rules"]}
        self.assertEqual(description["extends"], "rules_v0.2")
        self.assertGreaterEqual(description["rule_count"], 37)
        self.assertIn("obligation", description["enabled_anchor_types"])
        self.assertIn("relation", description["enabled_anchor_types"])
        self.assertIn("obligation.payment_timing", rule_ids)
        self.assertIn("obligation.data_return_deletion", rule_ids)
        self.assertIn("obligation.delivery_acceptance", rule_ids)
        self.assertIn("obligation.audit_cooperation", rule_ids)
        self.assertIn("obligation.subcontractor_flowdown", rule_ids)
        self.assertIn("relation.termination_data_return_dependency", rule_ids)
        self.assertIn("relation.payment_suspension_dependency", rule_ids)
        self.assertIn("relation.security_incident_remediation_dependency", rule_ids)

    def test_v0_3_generates_obligation_and_relation_anchors(self) -> None:
        text = (
            "Upon termination, Vendor shall return data within 30 days. "
            "Customer must pay undisputed invoices when payment due. "
            "The service level includes a service credit."
        )
        result = self.engine.scan_text(text, ruleset="rules_v0.3")
        obligation_rule_ids = {finding["rule_id"] for finding in result["obligation_anchors"]}
        relation_rule_ids = {finding["rule_id"] for finding in result["relation_anchors"]}
        self.assertEqual(result["anchor_capabilities"]["profile"], "v0.3")
        self.assertIn("obligation", result["anchor_capabilities"]["enabled_anchors"])
        self.assertIn("relation", result["anchor_capabilities"]["enabled_anchors"])
        self.assertIn("obligation.payment_timing", obligation_rule_ids)
        self.assertIn("obligation.data_return_deletion", obligation_rule_ids)
        self.assertIn("relation.termination_data_return_dependency", relation_rule_ids)
        self.assertIn("relation.sla_service_credit_dependency", relation_rule_ids)
        self.assertGreaterEqual(result["summary"]["obligation_anchors"], 2)
        self.assertGreaterEqual(result["summary"]["relation_anchors"], 2)

    def test_v0_3_thickened_rules_trigger_additional_obligation_and_relation_anchors(self) -> None:
        text = (
            "The deliverables are subject to acceptance criteria and acceptance testing. "
            "Vendor shall maintain insurance and provide certificate of insurance. "
            "Vendor must cooperate with audit and provide records. "
            "Confidentiality obligations survive termination, and residual knowledge is separately limited. "
            "Vendor shall ensure subcontractors comply and flow down obligations. "
            "If payment due is not made, Vendor may suspend services. "
            "A security incident requires Vendor to remediate."
        )
        result = self.engine.scan_text(text, ruleset="rules_v0.3")
        obligation_rule_ids = {finding["rule_id"] for finding in result["obligation_anchors"]}
        relation_rule_ids = {finding["rule_id"] for finding in result["relation_anchors"]}
        self.assertIn("obligation.delivery_acceptance", obligation_rule_ids)
        self.assertIn("obligation.insurance_coverage", obligation_rule_ids)
        self.assertIn("obligation.audit_cooperation", obligation_rule_ids)
        self.assertIn("obligation.confidentiality_survival", obligation_rule_ids)
        self.assertIn("obligation.subcontractor_flowdown", obligation_rule_ids)
        self.assertIn("relation.payment_suspension_dependency", relation_rule_ids)
        self.assertIn("relation.confidentiality_residual_exception", relation_rule_ids)
        self.assertIn("relation.security_incident_remediation_dependency", relation_rule_ids)
        self.assertIn("relation.audit_records_dependency", relation_rule_ids)

    def test_v0_3_semantic_validation_preserves_obligation_relation_summary(self) -> None:
        text = "Upon termination, Vendor shall return data within 30 days. The service level includes a service credit."
        result = self.engine.scan_text(text, ruleset="rules_v0.3")
        validated = SemanticValidatorService().validate_result(result, mode="validate")
        self.assertGreaterEqual(validated["summary"]["obligation_anchors"], 1)
        self.assertGreaterEqual(validated["summary"]["relation_anchors"], 2)

    def test_v0_3_enabled_anchors_can_disable_relations(self) -> None:
        result = self.engine.scan_text(
            "Upon termination, Vendor shall return data within 30 days.",
            ruleset="rules_v0.3",
            enabled_anchors="text,missing,risk,context,semantic,obligation",
        )
        self.assertIn("obligation", result["anchor_capabilities"]["enabled_anchors"])
        self.assertNotIn("relation", result["anchor_capabilities"]["enabled_anchors"])
        self.assertGreaterEqual(len(result["obligation_anchors"]), 1)
        self.assertEqual(result["relation_anchors"], [])

    def test_v1_ruleset_enables_action_capability(self) -> None:
        description = self.rule_loader.describe_ruleset("rules_v1.0")
        self.assertEqual(description["extends"], "rules_v0.3")
        self.assertIn("action", description["enabled_anchor_types"])
        self.assertIn("obligation", description["enabled_anchor_types"])
        self.assertGreaterEqual(description["rule_count"], 37)

    def test_v1_action_anchor_generation(self) -> None:
        text = (
            "Upon termination, Vendor shall return data within 30 days. "
            "Customer must pay undisputed invoices when payment due. "
            "The service level includes a service credit. "
            "This agreement includes unlimited liability."
        )
        result = self.engine.scan_text(text, ruleset="rules_v1.0")
        validated = SemanticValidatorService().validate_result(result, mode="validate")
        escalated = EscalationPolicyService().apply(validated, policy="default")
        actioned = ActionAnchorService().apply(escalated, policy="default")
        self.assertEqual(actioned["anchor_capabilities"]["profile"], "v1.0")
        self.assertGreaterEqual(len(actioned["action_anchors"]), 1)
        self.assertEqual(actioned["action_anchors"][0]["anchor_type"], "action")
        self.assertEqual(actioned["action_queue"]["item_count"], len(actioned["action_anchors"]))
        self.assertEqual(actioned["summary"]["action_anchors"], len(actioned["action_anchors"]))

    def test_v1_enabled_anchors_can_disable_actions(self) -> None:
        result = self.engine.scan_text(
            "This agreement includes unlimited liability.",
            ruleset="rules_v1.0",
            enabled_anchors="text,missing,risk,context,semantic,escalation,obligation,relation",
        )
        validated = SemanticValidatorService().validate_result(result, mode="validate")
        escalated = EscalationPolicyService().apply(validated, policy="default")
        actioned = ActionAnchorService().apply(escalated, policy="disabled")
        self.assertNotIn("action", result["anchor_capabilities"]["enabled_anchors"])
        self.assertEqual(actioned["action_anchors"], [])

    def test_enabled_anchors_can_narrow_profile(self) -> None:
        result = self.engine.scan_text(
            "This agreement includes unlimited liability and intellectual property in the work product belongs to Vendor.",
            ruleset="rules_v0.2",
            enabled_anchors="text,missing,context,risk",
        )
        self.assertNotIn("semantic", result["anchor_capabilities"]["enabled_anchors"])
        self.assertEqual(result["semantic_candidates"], [])
        rule_ids = {finding["rule_id"] for finding in result["findings"]}
        self.assertIn("contract.unlimited_liability", rule_ids)

    def test_v0_2_semantic_validation_and_escalation_anchors(self) -> None:
        result = self.engine.scan_text("All intellectual property in the work product belongs to Vendor.", ruleset="rules_v0.2")
        validated = SemanticValidatorService().validate_result(result, mode="validate")
        semantic_rule_ids = {finding["rule_id"] for finding in validated["semantic_anchors"]}
        self.assertIn("contract.ip_ownership_anomaly", semantic_rule_ids)
        self.assertEqual(validated["summary"]["semantic_anchors"], 2)

        escalated = EscalationPolicyService().apply(validated, policy="default")
        self.assertGreaterEqual(len(escalated["escalation_anchors"]), 1)
        self.assertEqual(escalated["escalation_anchors"][0]["anchor_type"], "escalation")

    def test_industry_overlay_adds_construction_rule(self) -> None:
        result = self.engine.scan_text("报价内不限量，但部分项目费用另计。", ruleset="rules_v0.1", industry_id="construction")
        rule_ids = {finding["rule_id"] for finding in result["findings"]}
        self.assertIn("construction.cost_escalation_risk", rule_ids)
        self.assertIn("construction.unlimited_item_trap", rule_ids)

    def test_grounding_service_adds_grounded_spans(self) -> None:
        text = "This agreement includes unlimited liability."
        result = self.engine.scan_text(text, ruleset="rules_v0.1")
        grounded = LangExtractGroundingService().ground_result(text, result, allow_network=False)
        finding = next(item for item in grounded["findings"] if item["rule_id"] == "contract.unlimited_liability")
        self.assertEqual(finding["evidence"]["grounding_source"], "local_exact")
        self.assertEqual(finding["evidence"]["grounded_spans"][0]["start"], text.index("unlimited liability"))
        self.assertEqual(grounded["grounding"]["provider"], "local_exact")

    def test_document_service_auto_falls_back_to_native_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "contract.txt"
            input_path.write_text("This agreement shall automatically renew.", encoding="utf-8")
            service = DocumentService(tmp_path / "uploads")
            text, meta = service.extract_text(str(input_path), backend="auto")
        self.assertIn("automatically renew", text)
        self.assertEqual(meta["extraction_backend"], "native")

    def test_pdf_renderer_creates_annotated_pdf(self) -> None:
        import importlib

        fitz = importlib.import_module("fitz")
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_pdf = tmp_path / "contract.pdf"
            output_pdf = tmp_path / "annotated.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 72), "This agreement includes unlimited liability.")
            document.save(input_pdf)
            document.close()

            service = DocumentService(tmp_path / "uploads")
            text, meta = service.extract_text(str(input_pdf), backend="native")
            result = self.engine.scan_text(text, ruleset="rules_v0.1")
            grounded = LangExtractGroundingService().ground_result(text, result, allow_network=False)
            render_result = PdfRenderer().render_annotated_pdf(str(input_pdf), grounded, meta["layout_map"], str(output_pdf))

            self.assertTrue(render_result["ok"])
            self.assertTrue(output_pdf.exists())

    def test_job_store_enforces_lawyer_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = JobStore(Path(tmp_dir) / "jobs.sqlite3")
            job_id = store.create_job(
                organization_id="org_a",
                workspace_id="workspace_a",
                created_by="lawyer_a",
                request={"organization_id": "org_a", "workspace_id": "workspace_a", "created_by": "lawyer_a"},
                status="completed",
            )
            job = store.get_job(job_id)
            allowed = assert_job_access(job, RequestScope(user_id="lawyer_a", organization_id="org_a", workspace_id="workspace_a"))
            self.assertEqual(allowed["job_id"], job_id)

            with self.assertRaises(HTTPException) as user_error:
                assert_job_access(job, RequestScope(user_id="lawyer_b", organization_id="org_a", workspace_id="workspace_a"))
            self.assertEqual(user_error.exception.status_code, 404)

            with self.assertRaises(HTTPException) as workspace_error:
                assert_job_access(job, RequestScope(user_id="lawyer_a", organization_id="org_a", workspace_id="workspace_b"))
            self.assertEqual(workspace_error.exception.status_code, 404)

    def test_audit_log_store_is_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = AuditLogStore(Path(tmp_dir) / "audit.sqlite3")
            scope_a = RequestScope(user_id="lawyer_a", organization_id="org_a", workspace_id="workspace_a")
            scope_b = RequestScope(user_id="lawyer_b", organization_id="org_a", workspace_id="workspace_a")
            event = store.record_event(
                scope=scope_a,
                event_type="action.update",
                resource_type="action",
                resource_id="AA-0001",
                metadata={"status": "completed"},
            )
            self.assertTrue(event["event_id"].startswith("audit_"))

            events_a = store.list_events(scope=scope_a, resource_type="action", resource_id="AA-0001")
            events_b = store.list_events(scope=scope_b, resource_type="action", resource_id="AA-0001")
            self.assertEqual(len(events_a), 1)
            self.assertEqual(events_a[0]["metadata"]["status"], "completed")
            self.assertEqual(events_b, [])

    def test_rule_draft_generator_creates_disabled_reviewable_rules(self) -> None:
        result = RuleDraftGenerator().generate(
            guide_text=(
                "律师指南：合同不得包含无限责任或 unlimited liability。"
                "涉及客户数据和训练模型的条款必须升级审核。"
            ),
            rule_scope="company",
            scope_id="acme_playbook",
            source_name="acme_review_guide",
            max_rules=5,
        )
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["rules_count"], 1)
        first_rule = result["rules"][0]
        self.assertFalse(first_rule["enabled"])
        self.assertEqual(first_rule["draft_status"], "needs_lawyer_review")
        self.assertTrue(first_rule["rule_id"].startswith("acme_playbook."))
        self.assertIn("trigger", first_rule)
        self.assertGreaterEqual(len(result["review_checklist"]), 3)
        self.assertIn("Generated rules are disabled", result["warnings"][0])


if __name__ == "__main__":
    unittest.main()
