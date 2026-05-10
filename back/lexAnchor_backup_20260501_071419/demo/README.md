# LexAnchor 合同风险锚点审查工具 - 技术指南 v0.1

## 1. 概述
LexAnchor 是一套专门为律师和企业法务设计的**合同风险自动发现与视觉取证系统**。与传统的关键词搜索不同，LexAnchor 采用“规则引擎扫描 + LLM 语义裁判”的双引擎架构，能够深度研判合同中的隐性陷阱（如不平衡的解除权、预算超支风险、品牌模糊等），并在 PDF 原件上生成精确的视觉锚点标注。

## 2. 核心架构 (Dual-Engine Strategy)
*   **第一引擎：LexRuleEngine (规则扫描)**: 基于行业预设的规则库，对合同进行毫秒级的全文本扫描。利用“否定抑制”逻辑排除如“除...之外不适用”等误报。
*   **第二引擎：LLM Semantic Referee (语义裁判)**: 针对规则引擎圈出的疑似片段，调度军火库（Arsenal）中的 A级/X级模型（如 Together 120B, Gemma 4 31B）进行深度法理逻辑研判，确保高准确率。
*   **视觉锚点系统 (Visual Anchoring)**: 自动计算风险片段在 PDF 中的物理坐标，生成带颜色分级的标注（严重风险用红框，一般风险用黄底），并自动插入一份“首页风险摘要”。

## 3. 审查锚点分类 (Anchor Categories)
系统目前支持以下 9 类核心法律锚点及行业专项规则：
*   **解除权 (Termination)**: 单方/无因解除权的对等性。
*   **争议解决 (Governing Law)**: 管辖法院与仲裁条款的明确性。
*   **责任限制 (Liability)**: 赔偿上限、间接损失豁免。
*   **行业陷阱 (Industry-Specific)**: 
    *   *装修/工程*: 增项费用另计风险、主材品牌模糊、不限量工程陷阱。
*   **缺失项监测 (Missing Clauses)**: 自动发现并提示合同中完全遗漏的关键条款。

## 4. 参数配置指南 (Parameter Specification)

| 参数 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| `file_path` | `string` | 是 | 待审查的 PDF 合同文件路径。 |
| `industry_id` | `string` | 否 | 行业专用规则集。默认 `construction`（装修工程）。支持 `it_service` 等。 |
| `org_id` | `string` | 否 | 企业/组织自定义规则集标识。 |

## 5. 快速上手示例 (Quick Start)

### 标准装修合同风险审查：
```bash
# 通过阿郎自然语言指令运行
阿郎，帮我审一下这个装修合同，行业设为 construction: "workspace/downloads/2.pdf"
```

### 直接调用工具入口：
```bash
运行工具 lex_anchor 参数 file_path="workspace/downloads/2.pdf" industry_id="construction"
```

## 6. 输出产物
*   **高亮 PDF (Annotated PDF)**: 在原件基础上增加红/黄颜色标注及首页摘要页。
*   **审查报告 (JSON Report)**: 包含所有风险项的法理依据、命中片段坐标及修改建议。

---
*注：本工具调用了军火库中的动态模型池，具备自动重试与降级能力（Together 120B <-> Gemma 4 31B），确保在复杂网络环境下审查不中断。*
