# LexAnchor (锚点) · 合同版 v0.1 - 解决方案与架构设计文档 (Updated)

## 1. 核心设计：三种锚定逻辑 (Anchor Methodology)
LexAnchor 不仅仅是“风险识别器”，更是“定位转换器”。根据法律逻辑的不同，定义了三种锚定方式：

| 风险类型 | 锚点类型 (`anchor_type`) | 视觉表现 | 判定主脑 |
| :--- | :--- | :--- | :--- |
| **存在型风险** (如：无限责任) | `text_span` | 原文段落红色边框 | 规则引擎 (Rule Engine) |
| **语义型风险** (如：IP归属) | `evidence_span` | **段落浅色背景 + 关键证据句深色高亮** | 规则圈选 + LLM 判定 |
| **缺失型风险** (如：缺管辖权) | `document_level` | **PDF 首页审查摘要区 (Summary Page)** | 规则全篇扫描 |

## 2. 关键工程决策
### 2.1 局部窗口否定抑制 (Negation Suppression)
为了提升规则引擎的信噪比，针对 Keyword 规则执行“抑制逻辑”：
- **逻辑：** 在命中关键词的前后 40 字符窗口内，扫描否定触发词（如：不适用、不构成、除...外）。
- **处理：** 若命中否定词，该风险标记为 `status: suppressed`，默认不显示在高亮 PDF 中，但保留在 JSON 证据链中供底层追溯。

### 2.2 LLM 证据链提取 (Evidence Extraction)
针对 `semantic` 规则，LLM 不仅输出“是非题”，还必须从原文中执行“最小必要证据摘录”：
- **约束：** LLM 必须返回原文中支撑其判断的精确短语（Evidence Spans）。
- **价值：** 实现细粒度渲染，让律师一眼看到“导致风险的那个词”。

## 3. 阿郎 (Alang) 模式下的输出形态
### 3.1 结构化 JSON 数据集
```json
{
  "findings": [
    {
      "rule_id": "contract.ip_ownership_anomaly",
      "anchor_type": "evidence_span",
      "page_num": 5,
      "bounding_boxes": [[100, 200, 400, 300]],
      "evidence_spans": [
        { "text": "全部知识产权归乙方所有", "importance": "core" }
      ],
      "reason": "条款将定制开发成果的 IP 强行划归 Vendor。",
      "recommendation": "修改为定制部分归甲方所有。"
    },
    {
      "rule_id": "contract.missing_termination",
      "anchor_type": "document_level",
      "location": null,
      "reason": "全篇未发现终止相关独立条款。",
      "recommendation": "补充终止机制。"
    }
  ]
}
```

### 3.2 视觉增强 PDF (`annotated_contract.pdf`)
- **首页摘要：** 插入一个自动生成的“结构审查封面”，列出所有 `document_level` 的缺失项。
- **双层渲染：** 段落层级使用淡粉色填充；核心证据短语（Evidence Spans）叠加深红色下划线。
