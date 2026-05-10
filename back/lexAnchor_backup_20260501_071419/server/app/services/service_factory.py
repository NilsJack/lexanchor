from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.services.action_anchor import ActionAnchorService
from app.services.anchor_engine import AnchorEngine
from app.services.audit_log import AuditLogStore
from app.services.context_detector import ContextDetector
from app.services.document_service import DocumentService
from app.services.escalation_policy import EscalationPolicyService
from app.services.job_store import JobStore
from app.services.langextract_grounding import LangExtractGroundingService
from app.services.pdf_renderer import PdfRenderer
from app.services.redaction_service import RedactionService
from app.services.report_service import ReportService
from app.services.rule_authoring import RuleDraftGenerator
from app.services.rule_loader import RuleLoader
from app.services.semantic_validator import SemanticValidatorService


@lru_cache(maxsize=1)
def get_rule_loader() -> RuleLoader:
    return RuleLoader(get_settings().rules_dir)


@lru_cache(maxsize=1)
def get_anchor_engine() -> AnchorEngine:
    return AnchorEngine(get_rule_loader(), ContextDetector())


@lru_cache(maxsize=1)
def get_job_store() -> JobStore:
    return JobStore(get_settings().database_path)


@lru_cache(maxsize=1)
def get_audit_log_store() -> AuditLogStore:
    return AuditLogStore(get_settings().database_path)


@lru_cache(maxsize=1)
def get_report_service() -> ReportService:
    return ReportService(get_settings().artifacts_dir)


@lru_cache(maxsize=1)
def get_document_service() -> DocumentService:
    return DocumentService(get_settings().uploads_dir)


@lru_cache(maxsize=1)
def get_redaction_service() -> RedactionService:
    return RedactionService()


@lru_cache(maxsize=1)
def get_grounding_service() -> LangExtractGroundingService:
    return LangExtractGroundingService()


@lru_cache(maxsize=1)
def get_semantic_validator() -> SemanticValidatorService:
    return SemanticValidatorService()


@lru_cache(maxsize=1)
def get_escalation_policy_service() -> EscalationPolicyService:
    return EscalationPolicyService()


@lru_cache(maxsize=1)
def get_action_anchor_service() -> ActionAnchorService:
    return ActionAnchorService()


@lru_cache(maxsize=1)
def get_pdf_renderer() -> PdfRenderer:
    return PdfRenderer()


@lru_cache(maxsize=1)
def get_rule_draft_generator() -> RuleDraftGenerator:
    return RuleDraftGenerator()
