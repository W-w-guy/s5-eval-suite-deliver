# S5-EVAL-004 要点命中评分器：关键词规则与评审模型双轨打分

## 一句话
`score_points(case, output) -> PointScore`，支持三种 match 方式（keyword / semantic / exact_field），
带 evidence_quote 回查、forbidden_points 一票否决、must 要点约束、3 轮多数投票与 judge_unstable 标记，
并在 30 条人工标注样本上做一致性自检（≥90% 才允许启用）。

## 目录
```
point_scorer/
  scorer.py     score_points 主实现（三种 match + 回查 + 否决 + 多数投票）
  model.py      评审模型调用层：地址只从 POINT_JUDGE_URL 读，强制本机/内网
  stub_judge.py 本地桩评审模型（可离线复现；支持 bad_quote 模式注入缺陷）
prompts/judge_prompt_v1.2.0.txt  评审提示词（带版本号，含逐字引用与不判金额约束）
data/consistency_30.jsonl        30 条人工标注的虚构一致性样本
tools/gen_samples.py             样本生成器（人工结论写死在表里，不由代码现算）
tools/check_consistency.py       一致性自检 + 报告生成 + 启用闸门
reports/consistency.{md,json}    一致性报告（含逐条对照表）
tests/                           53 个 pytest 用例
verify_1989.py                   4 条 AC 的 32 项断言
```

## 怎么跑
```bash
python tools/check_consistency.py     # 跑一致性自检，达标 rc=0
python -m pytest tests -q             # 53 个用例
python verify_1989.py                 # 32 项 AC 断言
```
用真实本地评审模型：
```bash
export POINT_JUDGE_URL=http://127.0.0.1:8080
python tools/check_consistency.py     # 换成真实模型后重跑一致率
```

## 实测

| AC | 要求 | 实测 |
|---|---|---|
| AC1 | 一致率 ≥90% 且附逐条对照表 | **93.62%（44/47）**，报告含 47 行逐条对照 |
| AC2 | evidence_quote 回查不到记 no | 编造引用 → 降级 no 并记入 `evidence_rejected`；无引用判 yes 同样降级 |
| AC3 | 命中 forbidden 得分再高也不通过 | 满分 1.0 + 命中 forbidden → `violation=True`、`passed=False` |
| AC4 | 3 次不一致带 judge_unstable | 3 轮全一致不标记；2:1 取多数但仍标记；平票取保守 |

## 五件必须先说清的事

**1. 一致率 93.62% 不是 100%，这是刻意的。**
留了 3 条真实口径分歧（CONS-017/018/021），都在「部分覆盖 vs 完全未覆盖」的边界上。
如果做成 100%，说明样本在迁就实现，这个指标就没有区分度了。
报告里逐条列出分歧并给出原因，**没有用一句通用文案糊过去**。

**2. 人工结论是写死在数据文件里的，不是代码算的。**
`data/consistency_30.jsonl` 的 `human` 字段由人生成（在本包里是手工构造的标注表）。
如果让代码现算人工结论，「一致率」就变成自己判自己 —— 这是这类交付物最容易作弊的地方。

**3. 关键词匹配必须识别否定。**
「本方案不涉及脱敏」里确实有「脱敏」两个字，但不算命中。
`scorer._kw_hit` 会检查关键词前 6 个字符内有没有「不涉及/不承诺/暂不」等否定词。

**4. 评审模型地址是代码硬拦，且未设置也拒绝。**
`model.check_endpoint()` 只允许 127./10./192.168./172./localhost/*.internal 等；
境外域名与公网 IP 在发请求前抛 `RejectEndpoint`。
**未设置 `POINT_JUDGE_URL` 也抛错** —— 静默 fallback 到某个默认公有云是最危险的行为。

**5. 金额不经过模型。**
提示词里显式写「不判断金额，金额类要点一律走 exact_field」，
`exact_field` 用严格相等（`128000` ≠ `12800000`，字符串 `"12800000"` ≠ 整数 `12800000`）。
模型侧即使看到金额要点也一律给 no，由程序接管。

## 已知分歧（如实列出）
| 用例 | 要点 | 人工 | 评分器 | 原因 |
|---|---|---|---|---|
| CONS-017 | P2 | partial | no | 只对导出数据脱敏：评分器只认「送模型前/入库前」这类明确范围 |
| CONS-018 | P1 | partial | no | 「尽快首响」：评分器不认「首响」为「响应」的同义表述 |
| CONS-021 | P1 | no | partial | 「响应时效另行约定」：评分器把明确推脱识别成含糊承诺 |

收敛办法是往提示词里加边界示例，不是调门槛。

## 与相邻工单的衔接
`data/consistency_30.jsonl` 的字段（case_id / output / points / human / forbidden_points）与
S5-EVAL 系列评测集同构；`score_points` 可直接被 #2612 的 visit_minutes runner 复用为「要点命中」评分环节，
把 `--prompt-version` 指过去即可，评测集不需要转换。

## 明文目录 files/（平台复核直读用）

本单同时提供 `files/` 明文目录：同一批内容摊成文本文件，供复核方直接读取，无需解压 zip。
`files/ACCEPTANCE.md` 是逐条验收对照表 —— 每条 AC 给出判定方式、复核命令与**实际输出原文**
（平台 `runtime_verified: false`，不会替你执行代码，所以贴真跑输出是唯一能让它看见证据的方式）。
