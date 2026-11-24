# 文档自动化评测报告 doc_auto.contract_fields

> 全部合同虚构；统一社会信用代码第 3–8 位固定 999999（不存在的区划码）；被测输出只进人工复核队列、不得直接对外发送；AI 不计算金额。

## 一、两项指标

| 指标 | 实测 | 门槛 | 判定 |
|---|---|---|---|
| 字段级准确率 | 0.9750 | ≥0.90 | 通过 |
| 错字段标红召回 | 0.7625 | ≥0.95 | **未通过** |

## 二、标红统计

| 项 | 值 |
|---|---|
| 识别错误的字段总数 | 15 |
| 其中未标红 | 10 |
| **错而未标红的 critical 字段** | **9**（目标 0） |
| 识别正确却被标红（误报） | 0 |

## 三、按字段的准确率

| 字段 | 正确 | 总数 | 准确率 |
|---|---|---|---|
| service_start | 30 | 40 | 0.7500 |
| party_b_name | 38 | 40 | 0.9500 |
| party_b_code | 39 | 40 | 0.9750 |
| payment_terms | 39 | 40 | 0.9750 |
| service_end | 39 | 40 | 0.9750 |
| amount_ex_tax | 40 | 40 | 1.0000 |
| amount_tax | 40 | 40 | 1.0000 |
| amount_total | 40 | 40 | 1.0000 |
| contract_no | 40 | 40 | 1.0000 |
| page_count | 40 | 40 | 1.0000 |
| party_a_code | 40 | 40 | 1.0000 |
| party_a_name | 40 | 40 | 1.0000 |
| seal_present | 40 | 40 | 1.0000 |
| sign_date | 40 | 40 | 1.0000 |
| tax_rate | 40 | 40 | 1.0000 |

## 四、错而未标红明细（单列，供人工复核）

| 用例 | 类型 | 未标红字段 | 其中 critical |
|---|---|---|---|
| CT-001 | generated | service_start | service_start |
| CT-003 | generated | service_start | service_start |
| CT-007 | generated | service_start | service_start |
| CT-013 | generated | service_start | service_start |
| CT-019 | generated | service_start | service_start |
| CT-025 | generated | service_start | service_start |
| CT-030 | difficult | service_start | service_start |
| CT-031 | difficult | service_start | service_start |
| CT-037 | difficult | service_start | service_start |
| CT-038 | difficult | party_b_name | - |

## 五、判定

**未达标：错字段标红召回 0.7625 < 0.95；错而未标红的 critical 字段 9 个（目标 0）**

## 六、按版式/载体的准确率

| 维度 | 值 | 用例数 | 字段准确率 |
|---|---|---|---|
| layout | minimal | 10 | 1.0000 |
| layout | standard | 10 | 0.9467 |
| layout | table_heavy | 10 | 0.9733 |
| layout | two_column | 10 | 0.9800 |
| carrier | docx | 13 | 0.9846 |
| carrier | scanned_pdf | 13 | 0.9897 |
| carrier | text_pdf | 14 | 0.9524 |