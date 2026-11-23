# ACCEPTANCE.md · 2264 S5-INTEL-034 情报评测脚本、指标报告与上线质量门槛

> 用途：把工单 4 条验收标准逐条落成「原文 / 判定方式 / 复核命令 / 实际输出原文」。
> 平台复核只读文本、不执行代码（runtime_verified=false），故每条都贴**真跑输出原文**。
> 全部样例虚构；包内不含客户名称；本文件命令均可在 `files/` 目录直接执行。

---

## AC1 原文

> 在虚构站点上运行生成 Markdown 与 JSON 报告，11 项指标齐全

**判定方式**（三重，缺一不算过）

1. `python -m intel_eval run --prompt-set v2` 退出码 **0**（11 项门槛全过）。
   > 为什么基线用 v2 而不用 v1：v1 是「首句」策略，摘要不含金额/比例，关键事实覆盖率实测 **0.0**，
   > 退出码 **1**。它是**故意保留的低分对照**，用来证明门槛真的会拦 —— 详见 AC4 之后的「两版对照」。
2. **同时**产出 `reports/intel_v2.md` 与 `reports/intel_v2.json` 两份文件 —— 不是只有其中一份。
3. JSON 的 `metrics` 里 **11 个键逐个存在**，且 Markdown 表格确实是 **11 行指标**（数行数，不是「看起来有」）。

**复核命令**

```bash
python -m intel_eval run --prompt-set v2      # 期望 rc=0
python -m intel_eval run --prompt-set v1      # 期望 rc=1（低分对照）
python verify_2264.py                          # AC1 共 17 项断言
```

**实际输出原文**

```
$ python -m intel_eval run --prompt-set v2
prompt_set=v2 entries=11 dropped=1 queued=0 crawl=discovered
  body_similarity          1.0        OK
  publish_date_accuracy    1.0        OK
  group_f1                 1.0        OK
  merge_errors             0          OK
  policy_type_accuracy     1.0        OK
  deadline_accuracy        1.0        OK
  key_fact_coverage        1.0        OK
  numeric_flagged_ratio    1.0        OK
  no_link_into_queue       0          OK
  robots_violations        0          OK
  urls_in_summary          0          OK
  pii_residue              0          OK
report=.../reports/intel_v2.md
THRESHOLD OK
```

```
$ python verify_2264.py      （节选 AC1 部分）
[ OK ] AC1 run 退出码 0（门槛全过） | rc=0
[ OK ] AC1 生成 Markdown 报告
[ OK ] AC1 生成 JSON 报告
[ OK ] AC1 JSON 里 11 项指标齐全（含归组 F1 的误合并约束）
[ OK ] AC1 Markdown 报告标题含「11 项指标」
[ OK ] AC1 Markdown 表格确实是 11 行指标 | 11
[ OK ] AC1 报告标注「正文提取平均相似度」
... （11 个指标名逐个断言）
[ OK ] AC1 报告同时给出归组误合并数
[ OK ] AC1 报告注明样例全部虚构
[ OK ] AC1 报告写明 AI 输出进复核队列、不对外发送
[ OK ] AC1 基线 11 项门槛全部达标
```

**约束与边界**

- 「11 项齐全」的判据是**硬编码键名清单**逐一 `in` 判断，不是 `len(metrics) >= 10` 这类模糊判断 —— 否则漏一项、多一项都能蒙过。
- Markdown 那侧用**数表格行数 == 11** 判定，避免「JSON 有但报告没渲染」的半成品。
- 第 3 项「转载归组 F1」实际是**两个数**（F1 与误合并数）合成一行显示、分开判定：F1 ≥ 0.95 **且** 误合并 == 0。只看 F1 会让「把所有文章归成一组」的退化解拿高分。
- 门槛是**双向可验**的：`THRESHOLDS` 表在 `intel_eval/metrics.py`，改门槛会同时改报告与退出码，不会出现「报告说通过、CI 说失败」两套口径。

---

## AC2 原文

> 生产配置下设置 INTEL_TEST_RESOLVER 时服务拒绝启动（有测试）

**判定方式**（fail-closed，不是 warning）

1. `APP_ENV=production` 且 `INTEL_TEST_RESOLVER` 非空 → `assert_safe_to_start()` 抛 `UnsafeConfigError`。
2. **CLI 退出码 3**（与「门槛不达标」的 1 区分开），stderr 打印 `REFUSE TO START`。
3. **拒绝启动时不产出任何报告** —— 只判「退出码非 0」不够，若进程崩之前已经把报告写出去，等于没防住。
4. **有对应单元测试且在测试集中实跑通过**（AC 原文括号里写「有测试」）。

**复核命令**

```bash
APP_ENV=production INTEL_TEST_RESOLVER="gov-a.example=127.0.0.1:8099" \
  python -m intel_eval run --prompt-set v1 ; echo "rc=$?"
python -m pytest tests -q          # 含 test_guard_robots_cli.py 的 guard 用例
```

**实际输出原文**

```
REFUSE TO START: 拒绝启动：APP_ENV=production 与 INTEL_TEST_RESOLVER=gov-a.example=127.0.0.1 同时存在。测试解析覆盖只允许在 test/dev 使用。
rc=3
```

```
$ python verify_2264.py
[ OK ] AC2 生产环境设置解析覆盖时直接抛错（fail-closed）
[ OK ] AC2 CLI 在生产+覆盖时退出码 3 且打印 REFUSE TO START | 3
[ OK ] AC2 拒绝启动时不产出报告
[ OK ] AC2 有对应测试且通过
```

**约束与边界**

- 三个变量都测：`APP_ENV=production` + 覆盖非空 → 拒绝；`APP_ENV=test` + 覆盖 → 放行；`APP_ENV=production` + 覆盖为空 → 放行。**只测「会拒绝」会漏掉「永远拒绝」的坏实现。**
- 解析映射额外限制只能指向 `127./10./192.168./172.` 内网段，填公网 IP 直接拒绝 —— 否则「测试覆盖」会变成对外发请求的后门。
- 退出码分开：`3` = 配置不安全拒绝启动，`1` = 门槛不达标。CI 里这两种要能区分（一个是改配置，一个是改质量）。

---

## AC3 原文

> 人为让一个 robots 禁止路径被抓取后 CI 任务退出码非 0（有测试）

**判定方式**

1. `--ignore-robots` 让抓取器**真的**去请求 `/admin/` 与 `/articles/draft/`（这两个目录在站点里真实存在）。
2. 指标第 9 项 `robots_violations` 从 0 变 **2**，报告该行判定为 `**未通过**`。
3. **退出码 1**（不是 0）。
4. 有对应测试：断言反例被检出，同时断言**正常模式下该指标恰为 0**（否则「指标恒为 0」也能让测试通过）。

**复核命令**

```bash
python -m intel_eval run --prompt-set ci_bad --ignore-robots ; echo "rc=$?"
python -m pytest tests -q
```

**实际输出原文**

```
$ python -m intel_eval run --prompt-set ci_bad --ignore-robots
  robots_violations        2          FAIL
THRESHOLD NOT MET: robots 禁止路径被抓取数
rc=1
```

```
$ python verify_2264.py
[ OK ] AC3 违反 robots 时退出码非 0 | 1
[ OK ] AC3 输出点名「robots 禁止路径被抓取数」
[ OK ] AC3 报告里 robots_violations >= 1 | 2
[ OK ] AC3 正常运行时 robots_violations == 0
[ OK ] AC3 有对应测试且通过
```

产物对照：`reports/intel_v2.json`（正常，0）与 `reports/intel_ci_bad.json`（故意犯规，2）**都在包里**，可直接对比，不必重跑。

**约束与边界**

- 这条 AC 的实质是**「指标能不能抓到自己的犯规」**。所以反例必须真跑抓取器、真命中禁止路径，而不是把 `robots_violations` 手工改成 2。
- 反例与正例都断言：只有「反例 = 2」会漏掉「永远报 2」的坏实现；`robots_violations == 0` 这一条就是防它。
- `--ignore-robots` 是**显式开关**，默认关闭且名字带 ignore，任何人一眼能看出这是用来演示犯规的，不是默认行为。

---

## AC4 原文

> 每个指标计算函数都有至少 2 个手算用例的单元测试

**判定方式**

1. **11 个指标函数逐个点名**（不是抽样），每个至少 2 个手算用例。
2. 用例是**手算**：期望值在测试里写成字面常量并在注释里给出算式，不是「跑一遍把输出抄进断言」。
3. 断言手算用例总数 ≥ 22（实测 **47**）。
4. 全部单元测试通过（实测 **79 passed**）。

**复核命令**

```bash
python -m pytest tests -q --collect-only     # 看用例数与分布
python -m pytest tests -q
python verify_2264.py
```

**实际输出原文**

```
$ python -m pytest tests --co
tests/test_guard_robots_cli.py::...            （18 条）
tests/test_metrics_handcalc.py::...            （41 条）
tests/test_rework_fixes.py::...                （20 条）
                                        → 合计 79 条

$ python -m pytest tests -q
........................................................................ [ 91%]
.......                                                                  [100%]
79 passed
```

```
$ python verify_2264.py
[ OK ] AC4 11 个指标都有对应用例 | ['test_m01','test_m02',...,'test_m11']
[ OK ] AC4 每个指标至少 2 个手算用例
[ OK ] AC4 手算用例总数 >= 22 | 47
[ OK ] AC4 全部单元测试通过
```

**约束与边界**

- 「至少 2 个」按**函数名到用例的映射**判定（`test_m01` … `test_m11` 各对应一个指标函数），不是按参数化条数蒙算 —— 一个用例里塞 5 组参数不算 5 个函数。
- 手算用例必须**含边界与退化输入**，否则测不到真问题。已覆盖：空输入、单元素、全一致、全无关、NDCG 反向序、误合并 0 与 1、abstain 不计入分母。
- **已知口径说明**：NDCG 用例最初手算写成 0.680627，与实算 0.680606 差 2.1e-5，原因是手算时 `log2(3)` 只取了 6 位；已按实算更正并在注释里留下这段过程。容差取 `1e-5`。

---

## 附：本包**没有**做的事（范围限制只写在这里）

- **被测模型是桩模型，不是真模型**。`intel_eval/extract.py:StubModel` 用确定性规则产出摘要与分类，目的是让整条评测链路可离线复现。因此报告里 1.0 的实测值证明的是**评测链路自洽**（数据 → 度量 → 门槛 → 退出码走通），**不等于**真实模型在这批数据上能拿 1.0。替换 `summarize()` / `classify()` 即可接真模型，12 项指标与门槛不动。
- 本包自带 12 篇最小虚构站点（`site/gov-a.example/`，含列表翻页、RSS、robots.txt、`<meta name="publish-date">`），**不依赖** S5-INTEL-033 的站点目录也能在干净机器跑通；`--site` 也可指向 033 的站点（同构）。
- 不实现真实的 DNS 解析覆盖（需要 root/hosts 权限）：改用 `INTEL_TEST_RESOLVER` 环境变量做进程内解析映射，且只允许内网段。
- 不做定时调度与报告归档（属 CI 侧职责），只提供 `.github/workflows/intel-eval.yml` 作为可直接用的合并拦截配置。
- 不计算任何金额（AI 不计算金额），摘要与报告里无金额字段。

---

## 附：提示词两版对照（证明 `--prompt-set` 真的改变了结果）

改造前，版本号只用作报告文件名，两版十二项指标完全相同 —— 评审据此判为 blocker。
现在版本真正进流水线：`v1` 取正文首句，`v2` 优先取含金额/比例的句子。

```bash
python -m intel_eval run --prompt-set v1 ; echo rc=$?    # rc=1
python -m intel_eval run --prompt-set v2 ; echo rc=$?    # rc=0
python -m intel_eval compare --a v1 --b v2
```

`reports/compare_v1_vs_v2.md` 原文（节选关键行）：

```
> - `v1`：首句基线版（取正文第一句。基线策略，不含金额/比例等关键事实。）
> - `v2`：关键事实优先版（优先取含金额/比例的关键事实句，没有则退回含截止日期的句子，再退回首句。）
| 摘要关键事实覆盖率 | 0.0 | 1.0 | +1 | >= 0.8 | 未通过 | 通过 |
总结：1 项变好，0 项变差。
```

即：**两版在同一批数据上走出了不同结论**（v1 覆盖率 0.0 → 不达标；v2 1.0 → 达标），
这是「版本传进了流水线」的直接证据，而不是把版本号写进文件名。

## 附：返工六条的逐条证据

| # | 意见 | 断言名 | 实测 |
|---|---|---|---|
| 1 | [blocker] prompt-set 没进流水线，compare 两版相同 | `test_stub_model_outputs_differ_by_prompt_set`、`test_compare_reports_real_difference`、`test_unknown_prompt_set_raises` | v1/v2 摘要不同；未知版本抛 `ValueError` 不静默退回 |
| 2 | [major] 第 8 项由金标字段决定，恒为 0 | `test_detect_original_link_dead` / `_live` / `_absent_field` / `_no_url`、`test_m08_counts_dropped_entries` | 四种页面形态各自判定；m08 输入含被丢弃条目 |
| 3 | [major] 第 7 项标出项与指标同规则，恒为 1.0 | `test_m07_uses_independent_rule`、`test_m07_drops_below_one_when_pipeline_misses`、`test_m07_partial`、`test_m07_date_triple_tolerates_formatting` | 流水线漏标时指标得 **0.0**（此前结构上不可能低于 1.0） |
| 4 | [major] 抓取清单取自金标 URL | `test_crawl_list_comes_from_discovery`、`test_gold_fallback_is_marked` | `crawl=discovered`；回退时明确标 `gold_fallback` |
| 5 | [minor] CI 文件只有 files/ 当根目录才触发 | 仓库根目录 `.github/workflows/intel-eval.yml`（含 `working-directory`） | 见仓库根 README 第六节 |
| 6 | [minor] m01 只测了 text_similarity | `test_m01_body_similarity_average_handcalc`、`test_m01_body_similarity_empty_and_single` | 多对求平均手算 0.75；空列表 0.0；单对 2/3 |

**每一条都配了「缺陷存在时会失败」的性质**，而不是只写一个能通过的断言：

- 意见 1：`test_compare_reports_real_difference` 断言两版 `key_fact_coverage` **不相等**，若版本没进流水线，这条必红。
- 意见 2：`test_detect_original_link_absent_field_means_own_article` 断言「没写原文链接 → 按本站原文」，
  若实现改成「没写就判无」，11 篇原创稿会被丢光，这条必红。
- 意见 3：`test_m07_drops_below_one_when_pipeline_misses` 构造「一条都没标」，断言指标 == 0.0，
  若仍用同一套规则算，这条必红。
- 意见 4：`test_gold_fallback_is_marked` 断言不传发现清单时必须标 `gold_fallback`，
  防止「悄悄照抄金标」而不被发现。
- 意见 6：手算值写死在注释里（0.75 = (1.0+0.5)/2），若把平均写成求和，这条必红。
