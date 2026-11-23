# DATA_PROVENANCE.md · 数据来源与可复核性

> 工单要求「示例数据虚构」。本文给出**生成脚本 + sha256 + 种子 + 重跑命令 + 产出规模 + pii 扫描结果**，让买家能自己复核，而不是只看到「全部虚构」四个字。

## 一、数据从哪来

本包**没有外部数据源，也没有联网抓取真实站点**。12 篇虚构政策文档 + 金标 + robots 探测清单，全部由一个生成器从内嵌常量产出：

| 项 | 值 |
|---|---|
| 生成脚本 | `tools/gen_site.py` |
| sha256 | `74eacc63cafdb368a20eceb9d19ec7e981f5deb3905d043c238e0d9b0880edf8` |
| 大小 | 11,216 字节 |
| 随机性 | **无随机数**。`random` 未被 import；组别/金额/日期全在 `GROUPS` 常量表里 |
| 外部依赖 | 仅标准库 `json` / `os` |
| 重跑命令 | `python tools/gen_site.py` |
| 重跑产出 | `site/gov-a.example/`（7 项 + 12 篇文章 + 1 篇 draft）+ `data/gold.jsonl`（12 行）+ `data/robots_probe.json` |
| 重跑幂等 | 已在**全新临时目录**重跑并逐文件比对 sha256：`data/gold.jsonl`、`robots_probe.json`、`index.html`、`robots.txt`、`rss.xml`、`a001.html`、`a012.html` **全部一致** |

为什么「无随机数」而不是「固定种子」：模板与金标本来就该是确定的；用随机数再固定种子只是把不确定性藏起来，读者还得信任种子。这里直接确定性生成，谁跑都一样。

## 二、产出规模（可直接数）

| 交付物 | 规模 | 可数方式 |
|---|---|---|
| 政策文档 | 12 篇（`articles/a001..a012.html`）+ 1 篇 robots 禁止的 draft | `ls site/gov-a.example/articles/*.html | wc -l` → 13（含 draft 子目录 1 篇时用 `find`） |
| 金标 | 12 行 JSONL | `wc -l data/gold.jsonl` |
| 转载组 | 4 组（C00~C03）各 2 篇 + 4 篇独立 | `python -c "import json,collections;print(collections.Counter(json.loads(l)['cluster_id'] for l in open('data/gold.jsonl')))"` |
| 列表页 | 2 页（`page-1.html` / `page-2.html`） | `ls site/gov-a.example/page-*.html` |
| RSS | 1 份（12 条 item） | `grep -c "<item>" site/gov-a.example/rss.xml` |
| robots 禁止路径 | 2 条（`/admin/`、`/articles/draft/`，且真实存在） | `cat site/gov-a.example/robots.txt` |
| 单元测试 | 79 个（18 guard/robots + 41 指标手算 + 20 返工回归） | `python -m pytest tests --co` |
| AC 断言 | 34 项 | `python verify_2264.py` |

## 三、虚构性怎么保证（三层）

### 第 1 层：域名与主体一律不可解析 / 不存在

- 站点域名 `gov-a.example` —— `.example` 是 **RFC 2606 保留 TLD**，DNS 永不解析。
- 企业名一律带「（虚构）」字样，如「示例云启科技有限公司（虚构）」「示例智联科技（虚构）」。
- 联系方式写 `010-XXXX-XXXX（示例号码，各字符为占位，不指向真实机构）` —— 字面就是占位符，不是真号码。

### 第 2 层：整包 pii 扫描（脚本判定，不靠人眼）

`tools/pii_scan.py` 扫描包内全部 `.py/.md/.json/.jsonl/.txt/.yml/.html/.xml`，四类形态：手机号 / 邮箱 / 18 位身份证 / 统一社会信用代码。

```
$ python tools/pii_scan.py
pii_scan files=53 raw_hits=10 allowed=10 unexpected=0
  ALLOWED DATA_PROVENANCE.md:62 email contact@***.invalid（RFC 2606 保留域）
  ALLOWED DATA_PROVENANCE.md:62 email a@b.***（RFC 2606 保留域）
  ALLOWED DATA_PROVENANCE.md:65 email a@b.***（RFC 2606 保留域）
  ALLOWED intel_eval/pipeline.py:39 email contact@***.invalid（RFC 2606 保留域）
  ALLOWED tests/test_metrics_handcalc.py:139 phone 138****1111
  ALLOWED tests/test_metrics_handcalc.py:141 email a@b.***
  ALLOWED tests/test_metrics_handcalc.py:169 phone 138****1111
  ALLOWED tests/test_metrics_handcalc.py:169 email a@b.***
  ALLOWED tests/test_metrics_handcalc.py:170 phone 138****1111
  ALLOWED tests/test_metrics_handcalc.py:172 email a@b.***
PII PASS（unexpected=0；手机/邮箱/身份证/信用代码 四类形态均无真实信息）
```

> 上面输出中的号码与邮箱**已在本文里掩码**（`138****1111` / `a@b.***`）。原因很直白：本文若原样引用扫描输出，文档自己就会成为新的命中源（实测过，`unexpected=5`）。原文可到 `tests/test_metrics_handcalc.py` 第 139/141/169/170/172 行查看。


**这 10 条 `ALLOWED` 是什么，逐类说明**：

- **4 条是 RFC 2606 保留域邮箱**（`contact@example.invalid`、`a@b.example`）：`.example` / `.invalid` 是保留 TLD，DNS 永不解析，白名单放行。其中 2 条出现在本文件的命令输出引用里（即引用自身输出，非新增数据）。
- **6 条在 `tests/test_metrics_handcalc.py`** —— **第 11 项指标「联系方式残留」的单元测试必须用「形如真实」的号码与邮箱，才能证明检测函数真的会报**。它们只作为被检测的坏值出现在测试里，不在任何交付内容（`site/` `data/` `reports/`）中，源码行尾标了 `# pii-scan:allow negative-fixture`，扫描器逐行判定并**单独打印豁免条数**，不会被静默吞掉。

**扫描器自身修过一版，如实记录**：白名单最初写成精确匹配 `{example.com, mail.invalid, ...}`，漏掉了 `a@b.example` 这类**保留 TLD 下的子域**，于是把自己本来虚构的地址报成命中（`unexpected=1`）。现改为按 TLD 判定（`.example` / `.invalid` / `.test` / `.localhost`）并保留二级域白名单，重跑 `unexpected=0`。这正是「扫描器也要被验」的例子 —— 一个只报 0 的扫描器和一个漏配正则的扫描器，输出长得一模一样。

**文件数是会变的**：`files=` 计入 `reports/` 下的生成物，跑过 `pytest` 或多次 `run` 后数量会涨（实测 45~58）。判据是 `unexpected=0`，不是某个固定文件数。

交付内容本体（`site/` + `data/` + `reports/`）扫描结果 **0 命中**。

### 第 3 层：不含客户名称

包内对「会员空间」「商务会员」「会员空间平台」做了全文扫描，**0 命中**（生成器早期版本写过「示例会员空间有限公司」，已替换为「示例云启科技有限公司」，因为后者擦边客户名称）。复核：

```bash
grep -rn "会员空间\|商务会员" . --include=*.py --include=*.md --include=*.json --include=*.html   # 期望无输出
```

## 四、数据设计为什么这么定（直接决定指标能否被测出来）

这不是「随便造 12 篇」，每一处设计都对应一个指标能不能被真测到：

| 设计 | 对应指标 | 若设计错了会怎样 |
|---|---|---|
| 前 8 篇组成 4 组跨来源转载，组内正文主干相同、只改标题与开头一句 | 转载归组 F1 | 组内文本毫无关系 → 金标自相矛盾，F1 永远上不去 |
| 后 4 篇各自独立（不同支持方向与金额） | 误合并数 = 0 | 全相似 → 归成一个组也能拿高 F1（退化解） |
| 缺原文链接的那篇**必须落在独立篇**上 | 无原文链接进队列数 = 0 | 放进转载组会让该组预测侧只剩 1 篇，召回被结构性压到 0.75，**数据缺陷冒充指标缺陷**（这一版初稿真踩过，已改） |
| 「行业动态」4 篇写成新闻体（无「申报截止」结构），金标 deadline 记 `_abstain` 不计入分母 | 截止日期准确率 | 硬塞日期进金标 → 测的就成了「能不能从新闻里抽出不存在的截止日」 |
| robots 禁止 `/admin/` 与 `/articles/draft/`，且目录**真实存在** | robots 违规数 | 目录不存在 → 抓也抓不到，`--ignore-robots` 演示跑不出 2 条违规，AC3 无法自证 |

## 五、可复核的一句话

```bash
python tools/gen_site.py        # 重跑生成，7 个关键产物的 sha256 与包内一致
python tools/pii_scan.py        # unexpected=0
python verify_2264.py           # 34/34
python -m pytest tests -q       # 79 passed
```

## 六、报告里的 1.0 说明什么、不说明什么（主动标注）

`reports/intel_v1.md` 里 11 项指标实测多为 `1.0`。**它说明的是评测链路自洽**：虚构站点 → 抓取（含 robots 门禁）→ 正文提取 → 分类 → 归组 → 日期抽取 → 摘要 → 核对项 → 度量 → 门槛 → 退出码，整条路径走得通，且指标会随输入变差而真的变红（`reports/intel_ci_bad_robots.json` 就是变红的实例）。

**它不说明**真实模型在这批数据上能拿 1.0 —— 被测模型是 `intel_eval/extract.py:StubModel`，用确定性规则产出摘要与分类，这样整条评测可离线复现。换成真模型只需替换 `summarize()` / `classify()`，指标与门槛不动。
