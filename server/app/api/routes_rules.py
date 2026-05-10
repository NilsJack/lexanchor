from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.services.access_control import assert_permission, scope_from_request
from app.services.service_factory import get_rule_loader

router = APIRouter(prefix="/api/v1/rulesets", tags=["rulesets"])


@router.get("")
def list_rulesets(request: Request) -> list[dict]:
    assert_permission(scope_from_request(request), "rule:read")
    return get_rule_loader().list_rulesets()


@router.get("/{ruleset_id}")
def describe_ruleset(
    request: Request,
    ruleset_id: str,
    industry_id: str | None = Query(None),
    org_id: str | None = Query(None),
) -> dict:
    assert_permission(scope_from_request(request), "rule:read")
    try:
        return get_rule_loader().describe_ruleset(ruleset=ruleset_id, industry_id=industry_id, org_id=org_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
