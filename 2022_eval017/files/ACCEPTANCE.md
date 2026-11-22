# 验收对应表（ACCEPTANCE）—— #2022 S5-EVAL-017 情报简报评测集 intel_brief.triage

四条验收标准逐条给：**判定方式 / 复核命令 / 实际输出原文**。
平台复核只读文本、不执行代码（`runtime_verified: false`），故此处贴真跑输出原文。
解压后在包根目录一条命令重跑全部断言：`python verify_2022.py`（Python 3.11+，零第三方运行时依赖）。

## 零、AC 编号对应表（必读）

本包 `verify_2022.py` 的内部标签与工单编号不完全一致，避免误读：

| 工单 AC | 原文要点 | 本包 verify 内部标签 |
|---|---|---|
| AC1 | 35 条、3 类分布、eval-lint 与 eval-pii-scan 通过 | `AC1 …`（同一编号） |
| AC2 | pairwise F1 / NDCG@5 脚本与 5 组手算一致（单元测试通过） | `AC2 …` 里的指标与破坏开关 + `pytest 全套通过` |
| AC3 | 每条用例至少含 1 组同事件多来源资讯（脚本统计输出） | `AC1 含同一事件多来源报道…`／`AC1 同事件报道措辞与日期都不同…` |
| AC4 | 用 echo mock 跑通 eval-run，报告中显示 3 项指标 | `AC2 runner 跑通…`／`AC2 报告含…`（三项指标） |

合计 **29 项断言**，全部通过。

---

## AC1　cases.jsonl 恰有 35 条，3 类分布与说明一致，eval-lint 与 eval-pii-scan 均通过

**判定方式**：数 `data/cases.jsonl` 行数=35；按 `kind` 分组须为 常规20/高相似干扰10/全无关5；
`tools/lint.py --lint` 与 `tools/lint.py --pii` 是**独立命令行工具**，各自 rc=0 且打印 `LINT PASS` / `PII PASS`
（不是只在 verify 里内联判断，买家可单独跑）。

lint 具体查 11 项：条数、分布、case_id 唯一、context 文件存在、资讯数 8~20、资讯 id 不重复、
profile 含 interests/industry、gold 聚类非空且覆盖全部资讯、gold 引用不得越界、gold_category 键与聚类一致、
全无关档 gold_top5 必须为空。pii 扫描 `.py/.md/.json/.jsonl/.yaml/.txt` 共 49 个文件，
号码规则只认 `1990000\d4` 虚构段、邮箱只认 `.invalid`，其余真实格式一律判泄露。

**复核命令**：`python tools/lint.py`（两个都跑）｜`python verify_2022.py`

**实际输出原文**：

```
[ OK ] AC1 每条 context 文件都存在 
[ OK ] AC1 cases.jsonl 恰有 35 条 | 35
[ OK ] AC1 分布 常规20/高相似干扰10/全无关5 | {'normal': 20, 'high_similarity': 10, 'irrelevant': 5}
[ OK ] AC1 每条 context 含 8~20 篇资讯 | 8..20
[ OK ] AC1 eval-lint 命令行 rc=0 且打印 PASS | LINT PASS
[ OK ] AC1 eval-pii-scan 命令行 rc=0 且打印 PASS | ['pii scanned=53 canary_hits=0 unexpected=0']
```

`python tools/lint.py` 命令行实际输出：

```
lint cases=35 distribution={'normal': 20, 'high_similarity': 10, 'irrelevant': 5} errors=0

LINT PASS

pii scanned=<N> canary_hits=0 unexpected=0

PII PASS
```

> `<N>` 为扫描文件数（干净解压后实测 49；跑过 pytest 会多出 `.pytest_cache` 里几个文件）。
> 断言不绑这个数，只认 `unexpected=0` 与 `PII PASS`——任何非虚构格式的手机号/邮箱/身份证都会让它 FAIL。

---

## AC2　pairwise F1 与 NDCG@5 脚本对 5 组手算样例结果一致（单元测试通过）

**判定方式**：不是只断言「指标 ≥0.80」，而是拿**手算期望值**去比对计算脚本。
`tests/test_metrics_handcalc.py` 共 16 个用例，期望值在注释里写出算式，例如：

- 金标 2 对、预测把 4 篇并成 1 簇（6 对）→ tp=2，P=2/6，R=1，**F1=0.5**，误合并 6-2=4
- 金标 1 簇 3 对、预测全拆开（0 对）→ **F1=0.0**，漏合并 3
- 簇编号完全不同（G1/P9）但内容一致 → 簇对齐后分类准确率必须是 **1.0**（不是 0）
- NDCG：金标 [a,b]、预测 [b,a]、gains a=2,b=1 → **0.7967075**
  （验算：ideal = 3 + 1/log₂3 = 3.630930；pred = 1 + 3/log₂3 = 2.892789；比值 0.7967075）

**复核命令**：`python -m pytest tests/test_metrics_handcalc.py -v`｜`python verify_2022.py`

**实际输出原文**：

```
[ OK ] AC2 聚类 pairwise F1 ≥0.80 | 0.8763
[ OK ] AC2 分类准确率 ≥0.80 | 0.8843
[ OK ] AC2 排序 NDCG@5 ≥0.80 | 0.8607
[ OK ] AC2 --break-cluster 能打掉 F1（指标可证伪） | 0.0000
[ OK ] AC2 --break-order 能打掉 NDCG@5 | 0.7317
[ OK ] pytest 全套通过 | ........................                
```

`python -m pytest tests/test_metrics_handcalc.py -v` 实际输出（节选）：

```
tests/test_metrics_handcalc.py ................                          [100%]

16 passed in 0.03s
```

**指标不是恒真的两处反证**（破坏开关实跑）：

```
--break-cluster : pairwise F1 0.8763 -> 0.0000，rc=1
--break-order   : NDCG@5     0.8607 -> 0.7317，rc=1
```

---

## AC3　每条用例至少含 1 组同事件多来源资讯（脚本统计输出）

**判定方式**：对每条用例检查 `gold_clusters` 里是否存在成员数 ≥2 的簇（即同一事件的多篇报道），
并进一步查「多来源三要素」——同一事件各篇的**措辞不同**（text 去重后条数等于成员数）、**日期不同**。
若两篇文案完全一样，聚类就退化成字符串比对，pairwise F1 没有区分度，这一档就等于白测。

**复核命令**：`python verify_2022.py`

**实际输出原文**：

```
[ OK ] AC1 含同一事件多来源报道的用例（≥30 条） | 35
[ OK ] AC1 同事件报道措辞与日期都不同（非复制粘贴） | 35
```

即 35 条用例**全部**含同事件多来源报道（要求 ≥30 条），且 35 条的措辞与日期都不相同。

---

## AC4　用 echo mock 跑通 eval-run，报告中显示 3 项指标

**判定方式**：`tools/eval_run.py` 用 `echo` provider（只用 context 与画像，**不读 gold**）跑通聚类→分类→按画像排序，
rc=0，并生成 Markdown 报告；报告里必须出现三项指标与阈值判定，且 forbidden 两项都要有数。

**复核命令**：`python tools/eval_run.py`｜`python verify_2022.py`

**实际输出原文**（`python tools/eval_run.py`）：

```
cases=35 threshold=0.50
pairwise_f1=0.8763 category_acc=0.8843 ndcg@5=0.8607 merge=55 split=21 forbidden=0/0
irrelevant 5/5 empty_top5
report=E:\Python\Agent_1\work\clawhunt\deliver\2022_triage\reports\triage_v1.md
THRESHOLD OK
```

**报告实存于包内** `reports/triage_v1.md`（明文可读，无需执行代码）。报告开头即三项指标：

```
| 指标 | 实测 | 门槛 | 判定 |
| 聚类 pairwise F1 | 0.8763 | ≥0.80 | 通过 |
| 分类准确率 | 0.8843 | ≥0.80 | 通过 |
| 排序 NDCG@5 | 0.8607 | ≥0.80 | 通过 |
```

对应断言原文：

```
[ OK ] AC2 runner 跑通（rc=0） | rc=0
[ OK ] AC2 生成报告（md） 
[ OK ] AC2 报告含「聚类 pairwise F1」 
[ OK ] AC2 报告含「分类准确率」 
[ OK ] AC2 报告含「排序 NDCG@5」 
[ OK ] AC2 报告含阈值敏感性表（默认值不是对着答案挑的） 
```

---

## 汇总

```
TOTAL 29, PASS 29, FAIL 0
```

## 附加说明（工单要求、不在四条 AC 编号内）

```
[ OK ] AC3 forbidden：同一事件出现两次 = 0 
[ OK ] AC3 forbidden：context 外资讯 = 0 
[ OK ] AC3 --leak 能触发 forbidden（检测有效） | 35
[ OK ] AC3 重复事件检测函数手算正确 | ['E1']
[ OK ] AC4 全无关样本 5 条 | 5
[ OK ] AC4 5 条全无关样本的 Top5 均为空（即输出「本期无高相关资讯」） | [[], [], [], [], []]
[ OK ] AC4 报告里单列无关样本统计 
```

## 一处必须说清的局限

「分类」与「排序」的评测在**簇对齐之后**进行（预测簇按成员重叠最大贪心匹配到金标簇），
所以它测的是「按簇判对没判对」，不测「簇编号命名」——这是有意设计。
但如果被测工具把两个真实不同的簇恰好切成与金标不同的粒度，对齐会退化，分类准确率会偏低：
这属于评测口径的已知边界，不在本套件能力范围外，但买家需要知道。

## 数据来源

35 条用例、12 份 context（内含 8~20 篇资讯）全部为**程序化虚构生成，无任何外部来源**，
无网络请求，不含真实个人或企业信息（企业名统一为「示例××」前缀），交付物中不出现客户名称。
生成脚本 `tools/gen_cases.py`，固定种子 `random.Random(2022)`，重跑命令 `python tools/gen_cases.py`——
重跑后 `data/cases.jsonl` 与 `contexts/*.json` 与本包逐字节一致（已在 Windows 与 Ubuntu 双平台各实测一次）。
详见 `DATA_PROVENANCE.md`。
