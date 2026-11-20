# S5-EVAL-022 知识问答评测集 kqa.retrieval

## 一句话
120 篇虚构知识文档 + 一键导入脚本 + 50 条用例（单文档 20 / 跨文档 12 / 数字日期 10 / 同义改写 8）
+ eval-lint 与 eval-pii-scan + 评测 runner，输出 recall@5、答案要点命中率、引用准确率三项指标。

## 目录
```
kb_docs/                 120 篇虚构知识文档（每篇带 doc_id/title/updated/visibility）
tools/gen_kb.py          文档生成器（与用例生成器共用 data/facts.json，保证金标可取证）
tools/gen_cases.py       50 条用例生成器（含分布与字段断言）
tools/import_kb.py       一键导入 SQLite 测试实例（--expect-empty 断言空实例）
tools/eval_lint.py       结构校验（50 条 / 分布 20-12-10-8 / gold 存在 / 要点是原句）
tools/eval_pii_scan.py   PII 扫描（占位号码不算命中）
tools/eval_run.py        评测 runner（BM25 检索 -> 作答带引用 -> 三项指标 + forbidden）
data/cases.jsonl         50 条用例
data/facts.json          文档事实表（生成器与用例共用的唯一真相源）
data/kb.sqlite3          知识库测试实例（可删，删掉即回到空实例）
suite.yaml               套件定义（含门槛与 forbidden_points）
reports/                 评测报告（md + json）
tests/                   pytest 用例
verify_2033.py           4 条 AC 的可执行断言
```

## 怎么跑
```bash
python tools/import_kb.py --reset --expect-empty    # 空实例 -> 导入 120 篇
python tools/eval_lint.py                           # 结构校验
python tools/eval_pii_scan.py                       # PII 扫描
python tools/eval_run.py                            # 评测，全达标 rc=0
python tools/eval_run.py --break-citation --tag bad # 故意引错，验证指标有效，rc=1
python -m pytest tests -q
python verify_2033.py                               # 4 条 AC 断言
```

## 实测

| 指标 | 实测 | 门槛 |
|---|---|---|
| 检索 recall@5 | **0.9200** | ≥0.85 |
| 答案要点命中率 | **0.8228** | ≥0.80 |
| 引用准确率 | **1.0000**（146 条引用） | ≥0.95 |
| forbidden：引用不在检索结果中的文档 | 0 | 0 |
| forbidden：数字与原文不一致 | 0 | 0 |

**指标不是永远好看的**：`--break-citation` 让 mock 故意引错文档，实测
引用准确率 **0.4589**、数字不一致 65 次、rc=1。这说明引用准确率真的在检查内容。

## 四件必须先说清的事

**1. 被测工具是 echo mock，不是真模型。**
`provider_echo` 只用检索结果里的段落作答并标注出处，不越出检索结果、不凭空生成。
所以它的 1.0000 引用准确率是**结构决定的**（引的都是真的存在的那一段），
不代表真实模型也这样。真模型的引用准确率一定会低于 1.0，那时这个指标才有区分度。

**2. 答案要点必须与问题一致 —— 这一条我踩过。**
初版问题是「…的开放时间与容量分别是多少？」，但答案要点有 3 条（含预约规则）。
第 3 条永远答不到，命中率被压在 0.35。这不是工具不行，是**金标与问题不一致**。
已改成问题把所有要点都问到；同义改写档也改成「一句话里问三个方面」。

**3. 同义改写档靠别名词表才能答到。**
问「静音舱最晚能待到几点」，文档小节写的是「开放时间」。
`eval_run.ALIAS` 提供「口语/同义 -> 小节标题」映射（真实 RAG 都有这一层）。
没有它，同义改写档的命中率是 0.125 —— 这正是这一档要考的能力。

**4. 检索用 BM25，标题做 5 倍字段加权。**
问题里常直接点名文档标题（"A 区 3 层 静音舱 使用规则 的…"），
标题不加权就顶不上来。这是 BM25F 的标准做法，**不读任何金标字段**。
recall@5 = 0.92 意味着有 4 条用例的金标文档没进前 5，报告逐条列出了。

## 已知局限（如实写）
- recall@5 = 0.92 而非 1.0：跨文档题里问题同时点名 2~3 篇文档，BM25 会把其中一篇挤出前 5。
  真实系统应做「标题精确匹配直通」或改混合检索（向量 + BM25）。
- 引用准确率判定用「数字全在 + 二元组覆盖 ≥0.6」，是**可脚本化的近似**，
  不是 EVAL-004 那种逐句语义判断。本包预留了 `support()` 作为判定接口，
  接 EVAL-004 评审模型时替换它即可，指标口径不变。
- 50 条只够验证链路与门槛，不够估置信区间。

## 与相邻工单的衔接
- 引用准确率的语义判定可换成 #1989（S5-EVAL-004）的评审模型：`support()` 换成调
  `point_scorer` 的 judge 即可，用例与指标不动。
- 知识文档的字段（doc_id/title/updated/visibility）与 #2254 虚构站点的标注字段可映射，
  站点文章可直接作为知识库来源之一。
