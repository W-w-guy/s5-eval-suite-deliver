# 回归基线管理与能力退化判定（S5-EVAL-034）

实现 `eval-baseline set / show / compare` 三个命令与退化判定函数：通过率差、平均分差、按 tag 的差值、翻转用例清单（regression / fix），含**抖动重跑**与**版本差异**处理。

## 一条命令复跑

```
python pkg/engine.py                    # 重算 data/（套件配置、基线、9 个运行场景）
python tools/verify.py                  # 逐条断言 AC（43 条），非零退出可接 CI
python -m pytest tests -v               # 单元测试（50 项）
python tools/mutate.py                  # 变异自检：改坏 13 处，每处都必须让 verify 变红
python tools/pii_scan.py                # PII 扫描
python tools/build_docs.py              # 由实跑结果重生成本文档与 ACCEPTANCE
python tools/make_zip.py                # 打包 + SHA256SUMS
```

依赖：Python 3.11+，无第三方库（YAML 用自写的极简子集解析器）。

## eval-baseline 用法

```
python -m pkg.cmd show
python -m pkg.cmd set --run BASE_V1 --reason "首版基线" --permissions eval.baseline.set
python -m pkg.cmd compare --run CUR_DROP4
python -m pkg.cmd compare --run CUR_FLAKY --json
```

退出码：**0 通过 / 1 判定为退化失败 / 2 命令报错**（基线不合法、权限不足、理由缺失、找不到运行）。
「命令报错」与「判定失败」是两种不同的退出码 —— 把非法基线当成退化失败会误导排查。

## set 的门槛

- 必须持有 `eval.baseline.set` 权限；
- 必须填写理由；
- 运行必须与当前套件同名、`suite_version` 相同、`status=completed` 且 `errors` 为空。

## 默认判定规则（可在 suite.yaml 覆盖）

| 判据 | 默认阈值 | 结果 |
| --- | --- | --- |
| 通过率下降 | > 3 个百分点 | **fail** |
| must 要点翻转用例数 | >= 3 条 | **fail** |
| 平均分下降 | > 0.05 | **warn** |
| 抖动重跑 | regression 用例重跑 2 次 | 任一次通过即标 flaky |

## 三条容易写错的口径

**① 通过率与分数差一律用分数精确计算，不先四舍五入再比较。**
`Fraction` 全程参与判定：降 3.2000pp 必须判失败。若写成 `round(drop) > 3`，3.2 会被舍成 3 从而假通过。`verify.py` 里有一条取整探针专门锁这件事。

**② flaky 用例不计入退化，且 `must` 与 `passed` 是解耦的。**
regression 用例重跑 2 次，任一次通过即标 flaky 并单列，既不算 regression 也不算 fix，也不计入 must 翻转数。另：用例判定失败不等于 must 要点翻转 —— 本包的数据里只有每第 3 条用例的 must 会跟随 passed，其余用例失败多因非 must 要点失分。这样「通过率降幅」与「must 翻转」是两条独立判据，一个场景失败不会被另一条顺带触发。

**③ suite_version 不同时只在共有的 case_key 上比较，并写明范围。**
直接用各自的全量通过率相比，会把「新增用例」和「已删除用例」算进分母，得出的降幅没有可比性（本包实测：v2 有 123 条、共有只有 113 条）。结果里会给出 `compared_cases` / `only_in_baseline` / `only_in_current` 与一句范围说明。

## 目录

| 路径 | 内容 |
| --- | --- |
| `pkg/baseline.py` | 基线门槛校验、退化判定、抖动处理、版本交集、Markdown 摘要 |
| `pkg/cmd.py` | `eval-baseline set/show/compare` 入口（退出码 0/1/2） |
| `pkg/engine.py` | 套件配置、基线运行、9 个场景（确定性生成） |
| `pkg/miniyaml.py` | 极简 YAML 子集解析器（零依赖；装了 PyYAML 时交叉验证） |
| `data/suite.yaml` | 套件配置与判定规则 |
| `data/runs/*.json` | 基线与 9 个场景运行记录 |
| `data/baselines/kb_qa.yaml` | 当前基线指针（run + 理由 + 设基人 + 时间） |
| `tests/` | pytest 用例 50 项 |
| `tools/` | 断言 / 变异 / 扫描 / 文档 / 打包 |

## 设计取舍

- **非法基线与退化失败用不同退出码**：前者是用法错误（2），后者是质量结论（1）。CI 里把两者混为一谈，会把「配错了基线文件」误报成「能力退化」。
- **豁免型的宽松处理一律做成显式开关**：`FLAKY_EXCLUDED_FROM_REGRESSION`、`ENFORCE_VERSION_INTERSECTION`、`ENFORCE_BASELINE_RUN_VALID` 都集中在 baseline.py，变异测试逐条翻转验证它们真的影响结论。
- **建议更新基线但不自动更新**：连续 3 次优于基线时只在报告里给建议。自动更新会让基线随能力下滑一路跟着降，退化判定失去基准。