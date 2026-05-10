# LexAnchor (锚点) · 合同版 v0.1 - 验收与测试方法文档

## 1. 验收目标
验证 LexAnchor 核心引擎能否基于 `rules_v0.1.yaml` 准确地从真实法律文书样本中“锚定” 9 个核心红旗条款，并在 PDF 渲染层产生精确的高亮输出。

## 2. 软件框架验收标准
系统必须实现基于以下四大组件的无缝数据流转：
1. **Extractor (提取器):** 能够将样本文档 (如 `sample_legal_document.pdf`) 转化为带 BBox 坐标索引的文本树。
2. **Rule Engine (规则引擎):** 能够在不调用 LLM 的情况下，100% 准确命中 `keyword` 和 `missing` 类型的规则。
3. **LLM Validator (LLM 验证器):** 针对 `semantic` 规则（如知识产权归属、审计权），大模型能结合上下文正确判定是否构成风险，有效过滤误报。
4. **Renderer (渲染器):** 能够将上述模块确定的风险条款，准确在 PDF 原文上绘制带颜色的高亮或边框。

## 3. 测试与验收过程设计

### 3.1 准备测试物料
利用工作区中已存在的现成文档作为基础物料：
- `workspace/TOOLS/legal_redaction_tool/sample_legal_document.pdf`

*若该文档中不包含足够的 SaaS/Vendor 协议特征（如缺少无限责任或审计权条款），开发团队需基于该 PDF 注入或追加几段典型的红旗条款文本以构造完整的验收样本 (`test_lexanchor_sample.pdf`)。*

### 3.2 单元验收 (Unit Validation)
- **极速规则命中测试:** 直接将一段包含“本协议不设任何赔偿上限”的纯文本输入 Rule Engine，验证其是否在毫秒级输出 `contract.unlimited_liability` 命中。
- **缺失规则探测测试:** 输入一段完全不包含“终止”或“管辖”字眼的文书文本，验证系统是否抛出 `missing_termination` 警告。
- **语义辨伪测试:** 输入“甲方有权进行审计，但每年不超过1次，且需提前30天书面通知”，验证 LLM Validator 能否正确将此条剔除出高危红旗池（即判定为合理条款）。

### 3.3 端到端验收 (End-to-End Validation)
开发团队需提供一个串联脚本（如 `test_lexanchor_e2e.py`），一键执行以下流程：
1. 读取测试用的 PDF 文件。
2. 调用提取器与规则引擎（加载 `rules_v0.1.yaml`）。
3. 触发 LLM 辅助验证。
4. 打印终端控制台的 Review Report，并生成一份 `test_annotated_contract.pdf`。

### 3.4 验收指标 (Metrics)
| 指标项 | V0.1 目标值 | 验证方式 |
| :--- | :--- | :--- |
| **规则命中准确率 (Recall)** | 100% | (Keyword/Missing 类型) 不能有漏报 |
| **语义判别准确度 (Precision)**| > 90% | (Semantic 类型) LLM 应成功过滤大多数合理条款 |
| **整体处理延迟** | < 10秒 / 10页 | 纯规则部分毫秒级，延迟应仅来源于少数并发的 LLM API 调用 |
| **锚点渲染精确度** | > 95% | 渲染出的红框能准确框住对应的文字段落，无严重偏移 |

## 4. 后续迭代
若 v0.1 测试验收通过，v0.2 将扩展至 30-50 个规则，并可为不同子类法务（如：劳动法务、采购法务）挂载不同的 YAML 规则文件。
