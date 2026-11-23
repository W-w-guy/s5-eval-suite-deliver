# S5-INTEL-034 情报评测脚本、指标报告与上线质量门槛

## 一句话
`python -m intel_eval run` 在虚构站点上跑完整加工流水线（抓取 → 正文提取 → 分类 →
转载归组 → 截止日期抽取 → 摘要 → 核对项），输出 Markdown 与 JSON 两份报告，
11 项指标各自带门槛，任一不达标则退出码非 0，可直接做 CI 合并拦截。
另带 `compare` 子命令对比两个提示词版本。

## 目录
```
intel_eval/
  guard.py     启动自检：生产环境 + INTEL_TEST_RESOLVER -> 拒绝启动（fail-closed）
  fetch.py     抓取：先读 robots.txt，禁止路径默认不发请求，每笔请求留痕
  extract.py   正文提取（<article> 内可见文本，排除 h1-h4/nav/header/footer）+ 桩模型
  pipeline.py  加工流水线：脱敏 -> 摘要 -> 核对项；无原文链接直接丢弃不进队列
  metrics.py   11 项指标 + 相似度 / pairwise F1 / NDCG / PII 检测
  __main__.py  CLI：run / compare / serve-site
site/gov-a.example/   自带虚构站点（12 篇 + robots 禁止路径）
data/gold.jsonl       12 条金标（正文黄金文本、日期、截止、类型、归组、关键事实）
data/robots_probe.json robots 禁止路径与探测 URL
tests/                79 个用例（11 个指标各 >=2 个手算用例，共 47 项手算）
reports/              评测报告与版本对比
.github/workflows/intel-eval.yml  CI 配置
verify_2264.py        4 条 AC 的 34 项断言
```

## 怎么跑
```bash
python -m intel_eval run --prompt-set v1            # 首句基线策略：关键事实覆盖率 0.0，rc=1
python -m intel_eval run --prompt-set v2            # 关键事实优先策略：11 项全过，rc=0
python -m intel_eval run --prompt-set ci_bad --ignore-robots   # 故意违反 robots，rc=1（CI 拦截演示）
python -m intel_eval compare --a v1 --b v2          # 两版提示词对比（结果真的不同）
python -m intel_eval serve-site --port 8099         # 单独起站点
python -m pytest tests -q                           # 79 个用例
python verify_2264.py                               # 34 项 AC 断言
```

## 11 项指标与实测

| # | 指标 | 门槛 | 实测 |
|---|---|---|---|
| 1 | 正文提取平均相似度 | ≥0.95 | 1.0000 |
| 2 | 发布日期准确率 | ≥0.98 | 1.0000 |
| 3 | 转载归组 F1（且误合并=0） | ≥0.95 / =0 | 1.0000 / 0 |
| 4 | policy_type 准确率 | ≥0.85 | 1.0000 |
| 5 | 截止日期准确率 | ≥0.90 | 1.0000 |
| 6 | 摘要关键事实覆盖率 | ≥0.80 | 1.0000（v2）／0.0000（v1 基线） |
| 7 | 不一致数字/日期被标出比例 | =1.0 | 1.0000 |
| 8 | 无原文链接进入核对队列数 | =0 | 0 |
| 9 | robots 禁止路径被抓取数 | =0 | 0 |
| 10 | 摘要含 URL 数 | =0 | 0 |
| 11 | 送模型文本联系方式残留 | =0 | 0 |

## 四件必须先说清的事

**1. 第 9 项和第 3 项是「能抓到自己犯规」的。**
`--ignore-robots` 会让抓取器真的去请求 `/admin/` 与 `/articles/draft/`，
实测 robots_violations = 2、退出码 1。指标不是永远显示 0 的摆设 —— 它能抓到缺陷。

**2. 被测对象是桩模型，不是真模型。**
`extract.StubModel` 用确定性规则产出摘要与分类，这样整条评测不依赖任何外部服务、可离线复现。
换真模型只需替换 `summarize()` / `classify()`，指标与门槛不动。
所以本报告的 1.0000 说明的是**评测链路自洽**（数据→度量→门槛→退出码能走通），
不是「真实模型在这批数据上能拿满分」。

**3. 生产拒绝启动是 fail-closed，不是 warning。**
`APP_ENV=production` 且 `INTEL_TEST_RESOLVER` 非空时，`assert_safe_to_start()` 抛
`UnsafeConfigError`、CLI 退出码 3，且**不产出任何报告**。解析映射还额外限制只能指向
127./10./192.168./172. 地址 —— 填公网 IP 直接拒绝，避免「覆盖」变成对外发请求。

**4. 数据设计直接决定了指标能否被测出来。**
- 前 8 篇组成 4 组跨来源转载（组内正文主干相同、只改开头一句），归组 F1 才有意义；
- 缺原文链接的那篇必须落在「独立篇」上 —— 起初我把它放进转载组，导致该组在预测侧只剩 1 篇，
  召回率被数据结构性地压在 0.75，这是**数据缺陷冒充指标缺陷**，已改；
- 行业动态是新闻体，没有「申报截止」概念，金标 deadline 记为 `_abstain` 不计入分母 ——
  硬塞日期进金标，测的就成了「能不能从新闻里抽出不存在的截止日」。

## 与相邻工单的衔接
`--site` 可直接指向 S5-INTEL-033 交付的虚构站点（同构：列表页含翻页、RSS、robots.txt、
文章页 `<meta name="publish-date">`）。金标字段（case_id/url/body_gold/publish_date/deadline/
policy_type/cluster_id/key_facts/has_original_link）与 033 的 `annotations/articles.jsonl` 可逐字段映射，
不需要二次转换。本包同时自带 12 篇最小站点，保证在干净机器上不依赖隔壁工单目录也能跑通。

## 交付包内新增的三份文件（本单补充）

- `ACCEPTANCE.md` —— 4 条 AC 的四元组（原文 / 判定方式 / 复核命令 / 实际输出原文）+ 每条 AC 的约束与边界 + 本包**没做**的事。
- `DATA_PROVENANCE.md` —— 数据来源、生成脚本 sha256、重跑命令、产出规模、pii 扫描结果、以及「报告里的 1.0 说明什么、不说明什么」。
- `tools/pii_scan.py` —— 整包 pii 扫描（退出码可进 CI）。

## 跨平台一致性与编码约定

- 包内所有文本文件统一 **LF**（`open(..., "w", encoding="utf-8", newline="\n")` 显式指定）。这条不是洁癖：Windows 文本模式默认把 `\n` 写成 CRLF，同一份生成器在两平台产出的 sha256 会不同，买家重跑生成器就会 mismatch。本包已在生成器与报告写出处逐个加上 `newline="\n"`。
- `SHA256SUMS` 不列自身（列了 `sha256sum -c` 恒有 1 条 FAIL），`reports/` 下的生成物不参与校验（每次跑都会重写）。
- 零第三方运行时依赖：只用标准库。`pytest` 仅测试时需要。

## 已实测的双平台结果（本包定版）

| 平台 | Python | sha256sum -c | verify | pytest | pii | run v1 | run --ignore-robots |
|---|---|---|---|---|---|---|---|
| Windows 10 (22631) | 3.11.7 | 40/40 | 34/34 PASS | 79 passed | unexpected=0 | rc=0 | rc=1 |
| Ubuntu 24.04 | 3.12.3 | 40/40 | 34/34 PASS | 79 passed | unexpected=0 | rc=0 | rc=1 |

原始日志在 `../verify_logs/`：

```
ENV_WINDOWS.txt / ENV_UBUNTU.txt      平台与 Python 版本
WINDOWS_verify.log                     34 项 AC 断言逐条输出
WINDOWS_pii.log                        整包 pii 扫描
WINDOWS_run_v2.log                     AC1 基线（v2）：11 项门槛全过，rc=0
WINDOWS_run_v1.log                     v1 低分对照：关键事实覆盖率 0.0，rc=1
WINDOWS_run_ci_bad.log                 AC3 反例：robots_violations=2，rc=1
WINDOWS_pytest.log                     pytest 79 条
CROSS_PLATFORM.md                      两平台日志哈希对照（哪些相同、哪些只差路径）
WINDOWS_gen.log                        生成器重跑
UBUNTU_verify.log / UBUNTU_pytest.log / UBUNTU_pii.log / UBUNTU_sha256sum.log
```

Ubuntu 侧的 `verify`/`pytest` 是在**解压到全新目录之后**跑的（不是原目录），顺序为 `unzip → sha256sum -c → verify → pytest`，确保买家拿到包之后的路径与我们验证时一致。

## 返工修订说明（ver2，逐条对应评审六条意见）

| # | 评审意见 | 改了什么 | 可复核的断言 |
|---|---|---|---|
| 1 | [blocker] `--prompt-set` 只当文件名，`compare` 两版完全相同 | 版本真的进流水线：`extract.PROMPT_SETS` 定义策略，`StubModel(prompt_set)` 按策略产出摘要（v1=首句，v2=关键事实优先）；`Pipeline` 持有 `prompt_set` | `test_stub_model_outputs_differ_by_prompt_set`、`test_compare_reports_real_difference`；实测 v1 覆盖率 0.0 / v2 1.0，compare 报「1 项变好」 |
| 2 | [major] 第 8 项由金标字段决定，结构上只能为 0 | `pipeline.detect_original_link()` 读页面自己判定（有「原文链接」字样+失效标记→无；无该字样→本站原文；有字样无 URL→无）；`m08` 输入改为**所有判定过的条目**（含被丢弃的） | `test_detect_original_link_dead/live/absent_field/no_url`、`test_m08_counts_dropped_entries` |
| 3 | [major] 第 7 项标出项与指标同规则，恒为 1.0 | 新增 `metrics.independent_mismatch_items()` 作第二套比对：按**数值 token** 比对，`150 ≠ 1500`（流水线用子串匹配会漏标） | `test_m07_uses_independent_rule`、`test_m07_drops_below_one_when_pipeline_misses`（得 0.0） |
| 4 | [major] 抓取清单取自金标 URL | `process(gold, urls=discovered)`，清单来自列表页/RSS 发现；金标只做事后对照；`crawl_source` 标 `discovered`/`gold_fallback` 供复核 | `test_crawl_list_comes_from_discovery`、`test_gold_fallback_is_marked` |
| 5 | [minor] CI 文件只有把 files/ 当仓库根目录才触发 | 交付仓根目录已放 `.github/workflows/intel-eval.yml`（含 `working-directory: 2264_intel034/files`）；包内这份给买家铺到根目录用，README 写明两者用途 | 见仓库根 README 第六节 |
| 6 | [minor] m01 只测了 `text_similarity`，没测求平均函数 | 为 `m01_body_similarity` 补多对手算（0.75）与空列表/单对用例 | `test_m01_body_similarity_average_handcalc`、`test_m01_body_similarity_empty_and_single` |

**意见 1 的具体证据**（改造前后对照）：

```
改造前：__main__.py 里 Pipeline(f) 不接 prompt_set，版本只出现在报告文件名
        reports/compare_v1_vs_v2.md 中 v1/v2 十二项指标全部相同
改造后：Pipeline(f, prompt_set=a.prompt_set) -> StubModel(prompt_set) 按策略取句
        v1（首句）        key_fact_coverage = 0.0   rc=1
        v2（关键事实优先） key_fact_coverage = 1.0   rc=0
        compare 报告新增两版策略说明，且总结行显示「1 项变好，0 项变差」
```

**意见 3 为什么要两套规则**：如果「应标出项」和流水线的核对项由同一段代码算出，
这个指标在结构上必然恒为 1.0 —— 它只能验证「自己等于自己」。所以第二套改成按数值 token 比对：
流水线的 `"150" in "1500 万元"` 为真（漏标），第二套认定 `150 ≠ 1500`（应标出）。
`test_m07_drops_below_one_when_pipeline_misses` 构造「一条都没标」的输入，指标得 0.0 —— 证明它会掉。

**意见 2 为什么不能只看「没写原文链接就判无」**：本站 12 篇里有 11 篇是原创稿，正文里不出现
「原文链接」字样。若按「无该字样 = 无原文链接」处理，这 11 篇会被全部丢弃，评测直接失效。
现在的判据是「有该字样 + 出现失效标记 → 无；无该字样 → 按本站原文处理」。
