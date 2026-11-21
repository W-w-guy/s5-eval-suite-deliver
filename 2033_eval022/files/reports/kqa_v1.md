# 知识问答评测集 kqa.retrieval 评测报告

> 知识库与问题全部虚构；被测工具输出只进复核队列、不直接对外发送；AI 不计算金额，费用类问题只引用知识库中的标准。

## 一、三项指标

| 指标 | 实测 | 门槛 | 判定 |
|---|---|---|---|
| 检索 recall@5 | 0.9200 | ≥0.85 | 通过 |
| 答案要点命中率 | 0.8228 | ≥0.80 | 通过 |
| 引用准确率 | 1.0000 | ≥0.95 | 通过 |

## 二、forbidden_points（任一出现即整条用例不通过）

| 项 | 次数 | 门槛 |
|---|---|---|
| 引用不在检索结果中的文档 | 0 | 0 |
| 数字与原文不一致 | 0 | 0 |

## 三、规模与口径

| 项 | 值 |
|---|---|
| 用例数 | 50 |
| 引用条数 | 146 |
| 有问题的用例 | 4 |
| 被测 provider | echo |
| top-k | 5 |

## 四、判定

**全部达标**

## 五、逐条结果（前 20 条）

| 用例 | 类型 | recall@5 | 引用准确的条数 | 问题 |
|---|---|---|---|---|
| KQA-A01 | single_doc | ✓ | 3/3 | - |
| KQA-A02 | single_doc | ✓ | 3/3 | - |
| KQA-A03 | single_doc | ✓ | 3/3 | - |
| KQA-A04 | single_doc | ✓ | 3/3 | - |
| KQA-A05 | single_doc | ✓ | 3/3 | - |
| KQA-A06 | single_doc | ✓ | 3/3 | - |
| KQA-A07 | single_doc | ✓ | 3/3 | - |
| KQA-A08 | single_doc | ✓ | 3/3 | - |
| KQA-A09 | single_doc | ✓ | 3/3 | - |
| KQA-A10 | single_doc | ✓ | 3/3 | - |
| KQA-A11 | single_doc | ✓ | 3/3 | - |
| KQA-A12 | single_doc | ✓ | 3/3 | - |
| KQA-A13 | single_doc | ✓ | 3/3 | - |
| KQA-A14 | single_doc | ✓ | 3/3 | - |
| KQA-A15 | single_doc | ✓ | 3/3 | - |
| KQA-A16 | single_doc | ✓ | 3/3 | - |
| KQA-A17 | single_doc | ✓ | 3/3 | - |
| KQA-A18 | single_doc | ✓ | 3/3 | - |
| KQA-A19 | single_doc | ✓ | 3/3 | - |
| KQA-A20 | single_doc | ✓ | 3/3 | - |