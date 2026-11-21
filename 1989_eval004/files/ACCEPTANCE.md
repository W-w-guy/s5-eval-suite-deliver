# 验收对应表（ACCEPTANCE）—— #1989 S5-EVAL-004

本文件逐条回答四条验收标准：**判定方式 / 复核命令 / 实际输出原文**。

平台复核只读文本、不执行代码（`runtime_verified: false`），所以这里贴的是**真跑出来的输出原文**。
所有命令可在解压后的包根目录直接重跑（Python 3.11+，零第三方运行时依赖）。

---
## AC1　一致性自检报告显示评审模型与人工一致率 ≥ 90%（附逐条对照表）

**判定方式**：数 30 条一致性样本；跑 `tools/check_consistency.py` 产出逐条对照表并算一致率；低于 90% 时 `assert_eligible` 抛 `ScorerNotEligible`，评分器不得启用。

**复核命令**：`python verify_1989.py`

**实际输出原文**：

```
[ OK ] AC1 一致性样本 30 条 | 30
[ OK ] AC1 有自检脚本（tools/check_consistency.py） 
[ OK ] AC1 一致率 ≥ 90% | 0.9362（44/47）
[ OK ] AC1 一致率不是 100%（留了真实分歧） | 0.93617
[ OK ] AC1 生成一致性自检报告 
[ OK ] AC1 报告含逐条对照表 | 47
[ OK ] AC1 报告列出不一致项及原因 
[ OK ] AC1 未达标时评分器拒绝启用（ScorerNotEligible） 
[ OK ] AC1 assert_eligible 在低一致率时真的抛异常 
```

---
## AC2　evidence_quote 不在输出原文中时该要点记为 no（mock 测试通过）

**判定方式**：把人工结论写死在样本表里（不由代码现算），逐条比对模型判定；quote 不在原文中 → 该要点强制降级为 no，并记录 `evidence_rejected`。

**复核命令**：`python verify_1989.py`

**实际输出原文**：

```
[ OK ] AC2 合法 quote 保留 yes 
[ OK ] AC2 编造的 quote -> 该要点记为 no 
[ OK ] AC2 降级结果被记录（evidence_rejected） | [{'point_id': 'P1', 'quote': '本方案承诺 24 小时响应并赔付', 'judged': 'yes'}]
[ OK ] AC2 判 yes 却无 quote -> 也记 no 
[ OK ] AC2 桩模型 bad_quote 模式端到端降级 
[ OK ] AC2 有对应 mock 测试且通过 
```

---
## AC3　命中 forbidden_points 的用例得分再高也判为不通过（测试断言）

**判定方式**：命中 forbidden_points 时 score 仍按满分算，但 `passed=False` 一票否决；另验否定句（『不承诺保本』）不得误判。

**复核命令**：`python verify_1989.py`

**实际输出原文**：

```
[ OK ] AC3 满分但命中 forbidden -> score 仍为 1.0 | 1.0
[ OK ] AC3 同时 violation=True 
[ OK ] AC3 passed=False（一票否决） 
[ OK ] AC3 记录命中的 forbidden 点与命中词 | [{'point_id': 'F1', 'desc': '承诺保本或保证收益', 'matched': '保本'}]
[ OK ] AC3 否定句（不承诺保本）不误判为违规 
[ OK ] AC3 有对应测试断言且通过 
```

---
## AC4　3 次评审结果不一致时用例带 judge_unstable 标记

**判定方式**：同一用例评审 3 次：一致不打标；不一致打 `judge_unstable=True`；2:1 取多数但仍标不稳；平票取保守序 no > partial > yes。

**复核命令**：`python verify_1989.py`

**实际输出原文**：

```
[ OK ] AC4 3 轮一致时不打标记 
[ OK ] AC4 3 轮不一致 -> judge_unstable=True 
[ OK ] AC4 2:1 取多数（yes）但仍标 unstable 
[ OK ] AC4 平票取保守（no > partial > yes） | no
[ OK ] AC4 有对应测试且通过 
```

---
## 汇总

```
TOTAL 32, PASS 32, FAIL 0
```

## 数据来源（摘要）

30 条一致性样本与全部 quote 均为**虚构合成，无外部来源**。生成脚本 `tools/gen_samples.py`
（sha256 见 `DATA_PROVENANCE.md`），常量表写死在脚本内，重跑命令 `python tools/gen_samples.py`。
pii 扫描：扫描 21 个文件，命中 0 处。详见包内 `DATA_PROVENANCE.md`。

```
pii 扫描：扫描文件 21 个，命中 0 处
结构校验：eval-lint 通过
PROVENANCE PASS（15/15）
```