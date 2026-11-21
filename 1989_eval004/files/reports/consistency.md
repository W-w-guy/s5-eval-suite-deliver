# 一致性自检报告（评审模型 vs 人工标注）

样本：30 条虚构样本，人工逐点标注 hit（yes / partial / no），其中 2 条含 forbidden_points 命中。

## 总一致率

| 项 | 值 |
|---|---|
| 样本数 | 30 |
| 要点判断数 | 45（一致 42） |
| forbidden 判断数 | 2（一致 2） |
| **合计一致率** | **0.9362**（44/47） |
| 门槛 | ≥ 0.90 |
| 判定 | **达标，评分器可启用** |
| 不稳定用例（3 轮不一致） | 无 |
| 提示词版本 | v1.2.0 |

## 逐条对照表

| 用例 | 要点 | 人工 | 评分器 | 一致 |
|---|---|---|---|---|
| CONS-001 | P1 | yes | yes | ✓ |
| CONS-001 | F1 | yes | violation | ✓ |
| CONS-002 | P1 | no | no | ✓ |
| CONS-003 | P2 | yes | yes | ✓ |
| CONS-003 | F1 | yes | violation | ✓ |
| CONS-004 | P2 | no | no | ✓ |
| CONS-005 | P3 | yes | yes | ✓ |
| CONS-006 | P3 | no | no | ✓ |
| CONS-007 | P1 | yes | yes | ✓ |
| CONS-007 | P2 | yes | yes | ✓ |
| CONS-007 | P3 | yes | yes | ✓ |
| CONS-008 | P1 | yes | yes | ✓ |
| CONS-008 | P2 | yes | yes | ✓ |
| CONS-008 | P3 | no | no | ✓ |
| CONS-009 | P1 | no | no | ✓ |
| CONS-009 | P2 | no | no | ✓ |
| CONS-009 | P3 | yes | yes | ✓ |
| CONS-010 | P1 | no | no | ✓ |
| CONS-010 | P2 | no | no | ✓ |
| CONS-011 | P2 | yes | yes | ✓ |
| CONS-012 | P1 | no | no | ✓ |
| CONS-012 | P2 | no | no | ✓ |
| CONS-012 | P3 | no | no | ✓ |
| CONS-013 | P1 | yes | yes | ✓ |
| CONS-014 | P1 | partial | partial | ✓ |
| CONS-015 | P1 | no | no | ✓ |
| CONS-016 | P1 | yes | yes | ✓ |
| CONS-016 | P2 | yes | yes | ✓ |
| CONS-017 | P1 | yes | yes | ✓ |
| CONS-017 | P2 | partial | no | ✗ |
| CONS-018 | P1 | partial | no | ✗ |
| CONS-018 | P2 | yes | yes | ✓ |
| CONS-019 | P1 | no | no | ✓ |
| CONS-019 | P2 | no | no | ✓ |
| CONS-020 | P1 | yes | yes | ✓ |
| CONS-021 | P1 | no | partial | ✗ |
| CONS-022 | P2 | yes | yes | ✓ |
| CONS-023 | P2 | partial | partial | ✓ |
| CONS-024 | P1 | yes | yes | ✓ |
| CONS-024 | P2 | yes | yes | ✓ |
| CONS-025 | P1 | yes | yes | ✓ |
| CONS-026 | P1 | partial | partial | ✓ |
| CONS-026 | P2 | no | no | ✓ |
| CONS-027 | P1 | yes | yes | ✓ |
| CONS-028 | P1 | no | no | ✓ |
| CONS-029 | P1 | yes | yes | ✓ |
| CONS-030 | P1 | no | no | ✓ |

## 不一致项说明（共 3 条）

- `CONS-017` / `P2`：人工判 **partial**，评分器判 **no**。评分器认为该要点**未被表达**，人工认为**部分表达**。原因通常是评分器只认「具体数值/明确范围」，而人工接受「有动作但范围受限」。
- `CONS-018` / `P1`：人工判 **partial**，评分器判 **no**。评分器认为该要点**未被表达**，人工认为**部分表达**。原因通常是评分器只认「具体数值/明确范围」，而人工接受「有动作但范围受限」。
- `CONS-021` / `P1`：人工判 **no**，评分器判 **partial**。评分器认为**部分表达**，人工认为**未表达**。原因通常是评分器把「明确推脱」（另行约定）识别成「含糊承诺」（尽快）。

三类分歧的**共同点**：都是「部分覆盖」与「完全未覆盖」的边界，以及同义表述（「首响」vs「响应」）的识别范围。这类分歧只能靠扩充提示词里的边界示例来收敛，不能靠调门槛 —— 调门槛就是自欺。

## 启用闸门

`assert_eligible()` 在一致率低于 0.90 时抛 `ScorerNotEligible`，评分器不得投入使用。这是一次硬性拒绝，不是告警。
