import sys
import os
import json
import time

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from extractor import run_extractor
from rule_engine import LexRuleEngine
from llm_validator import LexSemanticValidator
from renderer import LexRenderer
from langextract_grounding import ground_items_with_langextract

def list_industries():
    """列出目前军火库支持的所有行业规则标识"""
    projects_root = "workspace/TOOLS/LexAnchor"
    engine = LexRuleEngine(projects_root)
    industries = engine.list_available_industries()
    return {
        "ok": True,
        "available_industries": industries,
        "description": "目前已装配的行业规则库",
        "summary": f"当前可用行业规则库 {len(industries)} 个。",
    }

def run_lex_anchor(input_pdf: str, industry_id: str = None, org_id: str = None, backend_mode: str | None = None):
    projects_root = "workspace/TOOLS/LexAnchor"
    resolved_backend_mode = _normalize_backend_mode(backend_mode)
    
    # 极简模式：自动补全 industry_id
    if not industry_id:
        industry_id = "construction" # 默认装修行业
    
    # 模糊匹配逻辑 (简单处理：如果输入 '装修' 映射到 'construction')
    industry_map = {
        "装修": "construction",
        "工程": "construction",
        "IT": "it_service",
        "软件": "it_service"
    }
    industry_id = industry_map.get(industry_id, industry_id)

    print(f"\n[LexAnchor] 开始审查文件: {input_pdf} (行业: {industry_id})")
    start_time = time.time()

    # 1. Extractor: 提取文本与坐标
    print("[1/4] 提取原文并建立坐标索引...")
    extract_res = run_extractor(input_pdf, projects_root)
    if not extract_res["ok"]:
        return {"ok": False, "error": extract_res["error"]}
    
    full_text = extract_res["markdown_content"]
    layout_map = extract_res["layout_map"]

    # 2. Rule Engine: 极速扫描与缺失检测
    print("[2/4] 规则引擎扫描 (含否定抑制)...")
    engine = LexRuleEngine(projects_root)
    engine.load_rules(industry_id=industry_id, org_id=org_id)
    raw_findings = engine.scan_text(full_text)

    # 3. LLM Validator: 语义研判与证据提取
    print("[3/4] LLM 语义辅助研判与证据链提取...")
    validator = LexSemanticValidator(projects_root, backend_mode=resolved_backend_mode)
    final_findings = validator.validate_findings(raw_findings, full_text)
    final_findings, grounding_meta = _ground_findings(
        full_text,
        final_findings,
        allow_network=resolved_backend_mode == "network",
    )
    finding_stats = _summarize_findings(final_findings)

    # 4. Renderer: 生成高亮 PDF 与 报告
    print("[4/4] 渲染高亮 PDF 与 生成审查报告...")
    renderer = LexRenderer(projects_root)
    timestamp = int(time.time())
    output_pdf = os.path.join(projects_root, "reports", f"annotated_{timestamp}.pdf")
    report_path = os.path.join(projects_root, "reports", f"report_{timestamp}.json")
    
    renderer.render_annotated_pdf(input_pdf, final_findings, layout_map, output_pdf)
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(final_findings, f, ensure_ascii=False, indent=2)

    duration = time.time() - start_time
    print(f"\n[+] 审查完成! 耗时: {duration:.2f}s")
    summary = _build_summary(finding_stats, output_pdf, report_path)
    
    return {
        "ok": True, 
        "summary": summary,
        "outputs": {
            "output_pdf": output_pdf,
            "output_json": report_path,
        },
        "data": {
            "findings_count": finding_stats["visible_count"],
            "raw_findings_count": finding_stats["total_count"],
            "suppressed_count": finding_stats["suppressed_count"],
            "rule_count": finding_stats["rule_count"],
            "rule_counts": finding_stats["rule_counts"],
            "industry_applied": industry_id,
            "backend_mode": resolved_backend_mode,
            "model_route": resolved_backend_mode,
            "uses_network_model": resolved_backend_mode == "network",
            "grounding": grounding_meta,
        },
        "meta": {
            "input_file": input_pdf,
            "backend_mode": resolved_backend_mode,
            "model_route": resolved_backend_mode,
            "uses_network_model": resolved_backend_mode == "network",
        },
        "report_path": report_path, 
        "output_pdf": output_pdf, 
        "findings_count": finding_stats["visible_count"],
        "raw_findings_count": finding_stats["total_count"],
        "suppressed_count": finding_stats["suppressed_count"],
        "rule_count": finding_stats["rule_count"],
        "industry_applied": industry_id,
        "backend_mode": resolved_backend_mode,
        "model_route": resolved_backend_mode,
        "uses_network_model": resolved_backend_mode == "network",
        "grounding": grounding_meta,
    }


def _summarize_findings(findings: list[dict]) -> dict:
    records = [item for item in findings or [] if isinstance(item, dict)]
    visible = [item for item in records if item.get("status") != "suppressed"]
    rule_counts = {}
    severity_counts = {}
    anchor_counts = {}
    doc_level_count = 0
    span_level_count = 0
    for item in visible:
        rule_id = str(item.get("rule_id") or "unknown")
        rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1
        severity = str(item.get("severity") or "unknown")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        for anchor_name in _anchor_names_for_finding(item):
            anchor_counts[anchor_name] = anchor_counts.get(anchor_name, 0) + 1
        if item.get("anchor_type") == "document_level":
            doc_level_count += 1
        else:
            span_level_count += 1
    return {
        "total_count": len(records),
        "visible_count": len(visible),
        "suppressed_count": len(records) - len(visible),
        "doc_level_count": doc_level_count,
        "span_level_count": span_level_count,
        "rule_count": len(rule_counts),
        "rule_counts": dict(sorted(rule_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "severity_counts": dict(sorted(severity_counts.items(), key=lambda kv: kv[0])),
        "anchor_counts": dict(sorted(anchor_counts.items(), key=lambda kv: kv[0])),
    }


def _build_summary(stats: dict, output_pdf: str, report_path: str) -> str:
    visible_count = int(stats.get("visible_count") or 0)
    rule_count = int(stats.get("rule_count") or 0)
    suppressed_count = int(stats.get("suppressed_count") or 0)
    doc_level_count = int(stats.get("doc_level_count") or 0)
    span_level_count = int(stats.get("span_level_count") or 0)
    rule_counts = stats.get("rule_counts") if isinstance(stats.get("rule_counts"), dict) else {}
    anchor_counts = stats.get("anchor_counts") if isinstance(stats.get("anchor_counts"), dict) else {}
    top_rules = list(rule_counts.keys())[:3]
    top_labels = [_rule_label(rule_id) for rule_id in top_rules]

    summary = f"锚点审查已完成，形成 {visible_count} 个有效锚点，涉及 {rule_count} 类规则。"
    summary += f" 真实落点：页内锚点 {span_level_count} 个，文档级缺失锚点 {doc_level_count} 个。"
    layer_parts = []
    for name in ("Text Anchor", "Semantic Anchor", "Missing Anchor", "Context Anchor", "Risk Anchor", "Escalation Anchor", "Action Anchor"):
        count = int(anchor_counts.get(name) or 0)
        if count:
            layer_parts.append(f"{name} {count}")
    if layer_parts:
        summary += f" 锚点层次：{'；'.join(layer_parts)}。"
    if top_labels:
        summary += f" 主要锚点族：{'、'.join(top_labels)}。"
    if suppressed_count:
        summary += f" 另有 {suppressed_count} 个命中项被否定语境抑制，未在 PDF 标注。"
    summary += f" 标注PDF: {output_pdf}；JSON报告: {report_path}。"
    return summary


def _anchor_names_for_finding(item: dict) -> list[str]:
    anchor_type = str(item.get("anchor_type") or "").strip()
    names = []
    explicit = str(item.get("anchor_kind") or "").strip()
    if explicit:
        names.append(explicit)
    elif anchor_type == "document_level":
        names.append("Missing Anchor")
    elif anchor_type == "evidence_span" or item.get("requires_llm"):
        names.append("Semantic Anchor")
    elif anchor_type == "structural":
        names.append("Structural Anchor")
    else:
        names.append("Text Anchor")
    if item.get("context"):
        names.append("Context Anchor")
    if item.get("severity"):
        names.append("Risk Anchor")
    if item.get("category") == "obligation" or "义务" in str(item.get("rule_name") or ""):
        names.append("Obligation Anchor")
    if item.get("escalation") or str(item.get("severity") or "").lower() in {"critical", "high"}:
        names.append("Escalation Anchor")
    return names


def _rule_label(rule_id: str) -> str:
    return {
        "construction.unlimited_item_trap": "“不限量”范围陷阱",
        "construction.cost_escalation_risk": "变相增项/费用另计",
        "construction.brand_spec_vagueness": "品牌规格模糊",
        "contract.missing_termination": "缺少终止条款",
        "contract.missing_data_deletion": "缺少数据返还/删除条款",
        "contract.missing_governing_law": "缺少适用法律/管辖条款",
        "contract.unlimited_liability": "无限责任",
        "contract.indemnity_imbalance": "单方免责/赔偿不对等",
    }.get(str(rule_id or ""), str(rule_id or "未知规则"))

def _ground_findings(full_text: str, findings: list[dict], allow_network: bool | None = None) -> tuple[list[dict], dict]:
    targets = []
    for idx, finding in enumerate(findings or []):
        target_text = _finding_target_text(finding)
        if not target_text:
            continue
        targets.append({"text": target_text, "finding_index": idx})
    grounded_targets, meta = ground_items_with_langextract(full_text, targets, allow_network=allow_network)
    grounded_by_index = {
        item.get("finding_index"): item
        for item in grounded_targets
        if item.get("grounded_spans")
    }
    out = []
    for idx, finding in enumerate(findings or []):
        record = dict(finding)
        grounded = grounded_by_index.get(idx)
        if grounded:
            first_span = grounded["grounded_spans"][0]
            if record.get("location"):
                record["fallback_location"] = record.get("location")
            record["location"] = {"start": int(first_span["start"]), "end": int(first_span["end"])}
            record["grounding_source"] = "langextract"
        out.append(record)
    return out, meta


def _finding_target_text(finding: dict) -> str:
    if not isinstance(finding, dict) or finding.get("anchor_type") == "document_level":
        return ""
    matched = str(finding.get("matched_text") or "").strip()
    if matched:
        return matched
    for span in finding.get("evidence_spans") or []:
        if isinstance(span, dict):
            text = str(span.get("text") or "").strip()
            if text:
                return text
    return ""


def _normalize_backend_mode(value: object = None) -> str:
    inferred = _infer_backend_mode_from_text(value)
    return inferred or "local"


def _infer_backend_mode_from_text(*values: object) -> str | None:
    text = " ".join(str(value or "") for value in values).strip().lower()
    if not text:
        return None
    network_markers = ("网络模型", "联网模型", "联网", "network", "flash", "gemini", "google")
    local_markers = ("本地模型", "本地", "local", "ollama", "gemma4:e4b")
    if any(marker in text for marker in network_markers):
        return "network"
    if any(marker in text for marker in local_markers):
        return "local"
    return None

def run(file_path: str = None, industry_id: str = "construction", action: str = "run", **kwargs):
    """
    阿郎工具箱标准入口：分流 list 或 run 动作。
    """
    if action == "list" or file_path == "list":
        return list_industries()
    
    if not file_path:
        return {"ok": False, "error": "请提供需要审查的合同文件路径。"}
        
    backend_mode = kwargs.get("backend_mode") or _infer_backend_mode_from_text(
        kwargs.get("instructions"),
        kwargs.get("query"),
        kwargs.get("prompt"),
        kwargs.get("user_request"),
        kwargs.get("natural_language"),
    )
    return run_lex_anchor(file_path, industry_id=industry_id, backend_mode=backend_mode)


def run_tool(args: dict | None = None):
    payload = args if isinstance(args, dict) else {}
    file_path = payload.get("file_path") or payload.get("input_file") or payload.get("pdf_input")
    industry_id = payload.get("industry_id") or "construction"
    action = payload.get("action") or "run"
    extras = dict(payload)
    for key in ("file_path", "input_file", "pdf_input", "industry_id", "action"):
        extras.pop(key, None)
    return run(file_path=file_path, industry_id=industry_id, action=action, **extras)


def main(args: dict | None = None):
    return run_tool(args)

if __name__ == "__main__":
    # CLI 直接运行时保持原有逻辑
    if len(sys.argv) > 1:
        target_file = sys.argv[1]
        run_lex_anchor(target_file, industry_id="construction")
    else:
        print("Usage: python3 main_lex_anchor.py [pdf_path]")
