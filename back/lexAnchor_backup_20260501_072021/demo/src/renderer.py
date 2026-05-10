import fitz
import os
import importlib.util
from collections import Counter
from typing import List, Dict, Any

try:
    from .layout_index import rects_for_location
except ImportError:
    _layout_spec = importlib.util.spec_from_file_location(
        "lexanchor_layout_index",
        os.path.join(os.path.dirname(__file__), "layout_index.py"),
    )
    if _layout_spec is None or _layout_spec.loader is None:
        raise
    _layout_module = importlib.util.module_from_spec(_layout_spec)
    _layout_spec.loader.exec_module(_layout_module)
    rects_for_location = _layout_module.rects_for_location

class LexRenderer:
    """
    LexAnchor 渲染器：负责在 PDF 上绘制高亮框、下划线及生成首页摘要。
    """
    def __init__(self, projects_root: str):
        self.projects_root = projects_root

    def render_annotated_pdf(self, input_pdf: str, findings: List[Dict[str, Any]], layout_map: Dict[str, Any], output_pdf: str):
        """
        生成带标注的高亮 PDF
        """
        try:
            doc = fitz.open(input_pdf)
            
            # 1. 绘制页内锚点 (text_span & evidence_span)
            self._draw_page_annotations(doc, findings, layout_map)
            
            # 2. 生成并插入首页摘要 (document_level)
            self._insert_summary_page(doc, findings)
            
            # 保存
            os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
            doc.save(output_pdf, garbage=3, deflate=True)
            doc.close()
            return {"ok": True, "output_pdf": output_pdf}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _draw_page_annotations(self, doc, findings, layout_map):
        """
        在原文上绘制方框和高亮
        """
        for f in findings:
            if f.get("anchor_type") not in ["text_span", "evidence_span"] or f.get("status") == "suppressed":
                continue
            
            # 找到匹配文本的坐标
            # 注意：实际工程中需要根据 f['location']['start'] / f['location']['end'] 
            # 从 layout_map 中计算出对应的 BBoxes。此处简化逻辑。
            bboxes = self._get_bboxes_for_finding(f, layout_map)
            
            for page_num, rects in bboxes.items():
                if page_num >= len(doc): continue
                page = doc[page_num]
                for r in rects:
                    color = (1, 0, 0) if f['severity'] in ['critical', 'high'] else (1, 0.72, 0)
                    annot = page.add_highlight_annot(r)
                    annot.set_colors(stroke=color)
                    annot.set_opacity(0.22 if f['severity'] in ['critical', 'high'] else 0.18)
                    annot.update()
                    border = page.add_rect_annot(r)
                    border.set_colors(stroke=color)
                    border.set_border(width=0.7)
                    border.set_opacity(0.65)
                    border.set_info(content=f"{f.get('rule_id', 'LexAnchor')} {f.get('severity', '')}".strip())
                    border.update()

    def _insert_summary_page(self, doc, findings):
        """
        在 PDF 头部插入一页中文风险总览。页内锚点仍保留在原文位置。
        """
        visible = [f for f in findings if isinstance(f, dict) and f.get("status") != "suppressed"]
        if not visible:
            return

        summary_page = doc.new_page(0, width=595, height=842) # A4

        summary_text = "\n".join(
            str(block.get("text") or "").strip()
            for block in self._build_summary_lines(findings)
            if str(block.get("text") or "").strip()
        )
        summary_page.insert_textbox(
            fitz.Rect(44, 44, 552, 812),
            summary_text,
            fontsize=10.5,
            fontname="china-s",
            color=(0, 0, 0),
            align=0,
        )

    def _build_summary_lines(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        visible = [f for f in findings if isinstance(f, dict) and f.get("status") != "suppressed"]
        suppressed = [f for f in findings if isinstance(f, dict) and f.get("status") == "suppressed"]
        doc_level = [f for f in visible if f.get("anchor_type") == "document_level"]
        span_level = [f for f in visible if f.get("anchor_type") != "document_level"]
        rule_counts = Counter(str(f.get("rule_id") or "unknown") for f in visible)
        anchor_counts = self._anchor_system_counts(visible)

        blocks: List[Dict[str, Any]] = [
            {"text": "LexAnchor 锚点地图摘要", "fontsize": 18, "height": 28, "color": (0.75, 0, 0)},
            {"text": "本页只呈现本次文档中实际出现的锚点分布，不展开修改意见。正文高亮处为锚点真实所在。", "fontsize": 10, "height": 32},
            {
                "text": (
                    f"有效锚点 {len(visible)} 个：页内锚点 {len(span_level)} 个、缺失锚点 {len(doc_level)} 个；"
                    f"另有 {len(suppressed)} 个命中项被否定语境抑制，未在正文标注。"
                ),
                "fontsize": 11,
                "height": 42,
            },
            {"text": "Layer 1 感知锚（看见问题）", "fontsize": 13, "height": 22, "color": (0.75, 0, 0)},
            {"text": self._format_anchor_counts(anchor_counts, ("Text Anchor", "Semantic Anchor", "Structural Anchor", "Missing Anchor")), "fontsize": 10, "height": 30},
            {"text": "Layer 2 理解锚（理解问题）", "fontsize": 13, "height": 22, "color": (0.15, 0.15, 0.15)},
            {"text": self._format_anchor_counts(anchor_counts, ("Context Anchor", "Relation Anchor")), "fontsize": 10, "height": 30},
            {"text": "Layer 3 判断锚（判断问题）", "fontsize": 13, "height": 22, "color": (0.15, 0.15, 0.15)},
            {"text": self._format_anchor_counts(anchor_counts, ("Risk Anchor", "Obligation Anchor")), "fontsize": 10, "height": 30},
            {"text": "Layer 4 行动锚（处理问题）", "fontsize": 13, "height": 22, "color": (0.15, 0.15, 0.15)},
            {"text": self._format_anchor_counts(anchor_counts, ("Escalation Anchor", "Action Anchor")), "fontsize": 10, "height": 30},
            {"text": "锚点真实所在：规则分布", "fontsize": 13, "height": 22, "color": (0.15, 0.15, 0.15)},
        ]

        for idx, (rule_id, count) in enumerate(rule_counts.most_common(6), 1):
            sample = next((f for f in visible if str(f.get("rule_id") or "unknown") == rule_id), {})
            name = self._display_rule_name(sample)
            anchor_kind = self._anchor_kind_for_finding(sample)
            blocks.append({
                "text": f"（{idx}）{name}：{count} 个，类型 {anchor_kind}",
                "fontsize": 10,
                "height": 24,
            })

        if doc_level:
            blocks.append({"text": "结构性缺失", "fontsize": 13, "height": 22, "color": (0.75, 0, 0)})
            for idx, item in enumerate(doc_level[:5], 1):
                blocks.append({
                    "text": f"（{idx}）{self._display_rule_name(item)}：全文未发现对应条款；位置为文档级缺失锚点。",
                    "fontsize": 9.5,
                    "height": 36,
                })

        examples = self._representative_span_findings(span_level, limit=6)
        if examples:
            blocks.append({"text": "代表性页内锚点", "fontsize": 13, "height": 22, "color": (0.15, 0.15, 0.15)})
            for idx, item in enumerate(examples, 1):
                matched = self._compact_text(item.get("matched_text") or item.get("context"), 28)
                context = self._compact_text(item.get("context"), 54)
                blocks.append({
                    "text": f"（{idx}）{self._anchor_kind_for_finding(item)}｜{self._display_rule_name(item)}｜命中“{matched}”｜上下文“{context}”",
                    "fontsize": 9.5,
                    "height": 42,
                })

        blocks.append({
            "text": "锚点链路：Text → Meaning → Risk → Obligation → Decision → Action。v0.1 摘要只展示已被本次扫描实际落点支持的锚点。",
            "fontsize": 9,
            "height": 28,
            "color": (0.35, 0.35, 0.35),
        })
        return blocks

    @classmethod
    def _anchor_system_counts(cls, findings: List[Dict[str, Any]]) -> Counter:
        counts: Counter = Counter()
        for item in findings:
            kind = cls._anchor_kind_for_finding(item)
            counts[kind] += 1
            if item.get("context"):
                counts["Context Anchor"] += 1
            if item.get("severity"):
                counts["Risk Anchor"] += 1
            if item.get("category") == "obligation" or "义务" in str(item.get("rule_name") or ""):
                counts["Obligation Anchor"] += 1
            if item.get("escalation") or str(item.get("severity") or "").lower() in {"critical", "high"}:
                counts["Escalation Anchor"] += 1
        return counts

    @staticmethod
    def _format_anchor_counts(counts: Counter, names: tuple[str, ...]) -> str:
        parts = [f"{name}: {int(counts.get(name, 0))}" for name in names if int(counts.get(name, 0))]
        return "；".join(parts) if parts else "本次未形成该层显式锚点"

    @staticmethod
    def _anchor_kind_for_finding(finding: Dict[str, Any]) -> str:
        explicit = str(finding.get("anchor_kind") or "").strip()
        if explicit:
            return explicit
        anchor_type = str(finding.get("anchor_type") or "").strip()
        if anchor_type == "document_level":
            return "Missing Anchor"
        if anchor_type == "evidence_span" or finding.get("requires_llm"):
            return "Semantic Anchor"
        if anchor_type == "structural":
            return "Structural Anchor"
        return "Text Anchor"

    @staticmethod
    def _severity_label(severity: str) -> str:
        return {
            "critical": "重大",
            "high": "高",
            "medium": "中",
            "low": "低",
            "unknown": "未分级",
        }.get(str(severity or "unknown").lower(), str(severity or "未分级"))

    @staticmethod
    def _compact_text(value: object, limit: int = 60) -> str:
        text = " ".join(str(value or "").split())
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 1)].rstrip() + "…"

    @classmethod
    def _display_rule_name(cls, finding: Dict[str, Any]) -> str:
        name = str(finding.get("rule_name") or "").strip()
        if name:
            return cls._compact_text(name, 34)
        rule_id = str(finding.get("rule_id") or "unknown")
        fallback = {
            "construction.unlimited_item_trap": "“不限量”项目陷阱",
            "construction.cost_escalation_risk": "变相增项/费用另计风险",
            "construction.brand_spec_vagueness": "品牌/规格模糊风险",
            "contract.missing_termination": "缺少终止条款",
            "contract.missing_data_deletion": "缺少数据删除/返还条款",
            "contract.missing_governing_law": "缺少适用法律/管辖条款",
        }.get(rule_id)
        return fallback or rule_id

    @staticmethod
    def _representative_span_findings(findings: List[Dict[str, Any]], limit: int = 6) -> List[Dict[str, Any]]:
        selected: List[Dict[str, Any]] = []
        seen_rules: set[str] = set()
        severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        ordered = sorted(
            findings,
            key=lambda item: (severity_rank.get(str(item.get("severity") or "").lower(), 9), str(item.get("rule_id") or "")),
        )
        for item in ordered:
            rule_id = str(item.get("rule_id") or "unknown")
            if rule_id in seen_rules:
                continue
            selected.append(item)
            seen_rules.add(rule_id)
            if len(selected) >= limit:
                break
        return selected

    def _get_bboxes_for_finding(self, finding, layout_map) -> Dict[int, List[fitz.Rect]]:
        """
        根据字符偏移量计算 BBox
        """
        return rects_for_location(finding.get("location"), layout_map, padding=1.5)

if __name__ == "__main__":
    print("LexRenderer 模块加载成功。")
