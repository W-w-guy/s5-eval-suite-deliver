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
tests/                59 个用例（11 个指标各 >=2 个手算用例）
reports/              评测报告与版本对比
.github/workflows/intel-eval.yml  CI 配置
verify_2264.py        4 条 AC 的 34 项断言
```

## 怎么跑
```bash
python -m intel_eval run --prompt-set v1            # 默认门槛，全过则 rc=0
python -m intel_eval run --prompt-set v1 --ignore-robots   # 故意违反 robots，rc=1（CI 拦截演示）
python -m intel_eval compare --a v1 --b v2          # 两版提示词对比
python -m intel_eval serve-site --port 8099         # 单独起站点
python -m pytest tests -q                           # 59 个用例
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
| 6 | 摘要关键事实覆盖率 | ≥0.80 | 1.0000 |
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
| Windows 10 (22631) | 3.11.7 | 39/39 | 34/34 PASS | 59 passed | unexpected=0 | rc=0 | rc=1 |
| Ubuntu 24.04.5 | 3.12.3 | 39/39 | 34/34 PASS | 59 passed | unexpected=0 | rc=0 | rc=1 |

原始日志在 `../verify_logs/`：

```
ENV_WINDOWS.txt / ENV_UBUNTU.txt      平台与 Python 版本
WINDOWS_verify.log                     34 项 AC 断言逐条输出
WINDOWS_pii.log                        整包 pii 扫描
WINDOWS_run_v1.log                     AC1 基线：11 项门槛全过，rc=0
WINDOWS_run_ci_bad.log                 AC3 反例：robots_violations=2，rc=1
WINDOWS_gen.log                        生成器重跑
UBUNTU_verify.log / UBUNTU_pytest.log / UBUNTU_pii.log / UBUNTU_sha256sum.log
```

Ubuntu 侧的 `verify`/`pytest` 是在**解压到全新目录之后**跑的（不是原目录），顺序为 `unzip → sha256sum -c → verify → pytest`，确保买家拿到包之后的路径与我们验证时一致。
