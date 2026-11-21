# 验收对应表（ACCEPTANCE）—— #2033 S5-EVAL-022

本文件逐条回答四条验收标准：**判定方式 / 复核命令 / 实际输出原文**。

平台复核只读文本、不执行代码（`runtime_verified: false`），所以这里贴的是**真跑出来的输出原文**。
所有命令可在解压后的包根目录直接重跑（Python 3.11+，零第三方运行时依赖）。

---
## AC1　知识文档 120 篇 + 空实例导入成功

**判定方式**：`python tools/import_kb.py` 建库并统计表行数；docs=120、sections=720；空实例（无文档的库）也要能导入且不报错。

**复核命令**：`python verify_2033.py`

**实际输出原文**：

```
[ OK ] AC1 知识文档恰有 120 篇 | 120
[ OK ] AC1 导入脚本在空实例上执行成功（rc=0） | rc=0
[ OK ] AC1 命令输出显示导入前为空 | ['before: docs=0']
[ OK ] AC1 命令输出显示导入后 120 篇 | True
[ OK ] AC1 实例内 doc 数确为 120 | 120
[ OK ] AC1 每篇带 doc_id/标题/更新日期/可见范围 
[ OK ] AC1 可见范围标签存在且非单一值 | {'all': 90, 'member': 30}
```

---
## AC2　50 条用例 + 4 类分布 + lint/pii 通过

**判定方式**：数 `data/cases.jsonl` 50 条并核对四类分布；`eval-lint` 查字段，`eval-pii-scan` 扫手机号/邮箱/身份证。

**复核命令**：`python verify_2033.py`

**实际输出原文**：

```
[ OK ] AC2 cases.jsonl 恰有 50 条 | 50
[ OK ] AC2 4 类分布 20/12/10/8 | {'single_doc': 20, 'multi_doc': 12, 'numeric_date': 10, 'paraphrase': 8}
[ OK ] AC2 eval-lint 通过（0 错误） 
[ OK ] AC2 eval-lint 命令行 rc=0 且打印 PASS 
[ OK ] AC2 eval-pii-scan 通过（0 命中） | ['PII PASS']
[ OK ] AC2 lint 能抓到坏金标（gold 文档不存在） 
[ OK ] AC2 lint 能抓到凭空编造的答案要点 
```

---
## AC3　gold_doc_ids 全部在知识库中找到

**判定方式**：逐条取 `gold_doc_ids`，在 `kb_docs/` 与 sqlite 中双重确认存在，缺一即失败。

**复核命令**：`python verify_2033.py`

**实际输出原文**：

```
[ OK ] AC3 每条用例的 gold_doc_ids 都能在知识库中找到 
[ OK ] AC3 每条 gold_doc_ids 数量在 1~3 
[ OK ] AC3 每条 answer_points 数量在 3~5 
[ OK ] AC3 每个答案要点都能在 gold 文档里逐字找到 
```

---
## AC4　echo mock 跑通 eval-run 显示 recall@5

**判定方式**：`python -m tools.eval_run`（或包内 runner）用 echo mock 跑通，退出码 0，报告输出 recall@5。

**复核命令**：`python verify_2033.py`

**实际输出原文**：

```
[ OK ] AC4 用 echo mock 跑通 eval-run（rc=0） | rc=0
[ OK ] AC4 输出含 recall@5 与 citation 
[ OK ] AC4 生成 Markdown 报告 
[ OK ] AC4 报告写明「检索 recall@5」 
[ OK ] AC4 报告写明「引用准确率」 
[ OK ] AC4 报告写明「答案要点命中率」 
[ OK ] AC4 报告列出 forbidden_points 两项 
[ OK ] AC4 三项指标均达标 | recall=0.9200 point=0.8228 cite=1.0000
[ OK ] AC4 forbidden 两项均为 0 
[ OK ] AC4 引用准确率可被证伪（--break-citation 时 <0.95 且触发 forbidden） | cite=0.4589 num=65
[ OK ] AC4 pytest 全套通过 | ....................                    
```

---
## 汇总

```
TOTAL 29, PASS 29, FAIL 0
```

pytest 实跑：`python -m pytest tests -q`

```
....................                                                     [100%]
```

## 数据来源（摘要）

120 篇知识文档与 50 条用例全部为**虚构合成，无外部来源**：不使用公开数据集、不抓取网页、不使用客户数据。
生成脚本 `tools/gen_kb.py` + `tools/gen_cases.py`（sha256 见 `DATA_PROVENANCE.md`），
由 `data/facts.json` 确定性派生，重跑命令见该文件。pii 扫描：扫描 144 个文件，命中 0 处。

```
PROVENANCE PASS（16/16）
```