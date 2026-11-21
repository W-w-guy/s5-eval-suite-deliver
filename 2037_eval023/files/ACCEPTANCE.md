# 验收对应表（ACCEPTANCE）—— #2037 S5-EVAL-023

本文件逐条回答四条验收标准：**判定方式 / 复核命令 / 实际输出原文**。

平台复核只读文本、不执行代码（`runtime_verified: false`），所以这里贴的是**真跑出来的输出原文**。
所有命令可在解压后的包根目录直接重跑（Python 3.11+，零第三方运行时依赖）。

---
## AC1　cases.jsonl 恰有 30 组对话，每组 3–5 轮，4 类分布与说明一致

**判定方式**：数 30 组、每组 4 轮；四类分布 指代 8 / 条件变更 8 / 话题切换 6 / 纠正 8。

**复核命令**：`python verify_2037.py`

**实际输出原文**：

```
[ OK ] AC1 cases.jsonl 恰 30 组 | 30
[ OK ] AC1 每组 3–5 轮 | min 4 / max 4
[ OK ] AC1 分布 指代8/条件变更8/话题切换6/纠正8 | {'coref': 8, 'condition_change': 8, 'topic_switch': 6, 'correction': 8}
[ OK ] AC1 用例为 turns 数组格式 
[ OK ] AC1 复用 EVAL-022 知识库夹具（120 篇） | 120
[ OK ] AC1 每条引用的 kb_doc 都存在于知识库 
```

---
## AC2　eval-lint 与 eval-pii-scan 均通过（命令输出）

**判定方式**：`python tools/lint.py` 同时跑 eval-lint 与 eval-pii-scan，两者都要 PASS 且给出扫描文件数与命中数。

**复核命令**：`python verify_2037.py`

**实际输出原文**：

```
[ OK ] AC2 eval-lint 命令行 rc=0 且打印 PASS 
[ OK ] AC2 eval-pii-scan 命令行通过（0 命中） 
[ OK ] AC2 lint 内部复核 0 错误 
```

---
## AC3　8 组纠正类对话都把被纠正前提写入 forbidden_points（脚本检查）

**判定方式**：不只查字段存在，而是逐组比对：`forbidden_points` 必须包含该组第 2 轮被纠正掉的那个旧前提值，且旧值 ≠ 新值。

**复核命令**：`python verify_2037.py`

**实际输出原文**：

```
[ OK ] AC3 纠正类恰 8 组 | 8
[ OK ] AC3 8 组纠正类全部写入 stale_premise* 的 forbidden_points | 8/8
[ OK ] AC3 每条都指明被纠正的实体（wrong_entity） | 8/8
[ OK ] AC3 每条都记录被纠正的具体值（wrong_value） | 8/8
[ OK ] AC3 被纠正的旧值 ≠ 纠正后的新值（防 forbidden 恒假阳性） 
```

---
## AC4　用 echo mock 按轮次跑通 eval-run，结果中可见每轮的检查点

**判定方式**：`python -m multiturn` 按轮次调用并携带历史，输出三项指标；每个检查点挂在提问轮上，报告里逐轮可见。

**复核命令**：`python verify_2037.py`

**实际输出原文**：

```
[ OK ] AC4 echo mock 跑通 eval-run（rc=0） | rc=0
[ OK ] AC4 生成 Markdown 报告 
[ OK ] AC4 报告含「中间检查点」小节（逐轮可见） 
[ OK ] AC4 报告含三项指标 
[ OK ] AC4 三项指标均达标 | final=1.0000 cp=1.0000 forbidden=0
[ OK ] AC4 每条用例的检查点轮次可定位 | 30
```

---
## 汇总

```
TOTAL 25, PASS 25, FAIL 0
```

**eval-run 实际输出原文**（`python -m multiturn`）：

```
cases=30 facts=120
  final_point_hit    1.0000
  checkpoint_pass    1.0000
  forbidden          0
report=C:\Users\MSI\AppData\Local\Temp\tmpg4_vh0gv\reports\mt_v1.md
THRESHOLD OK
```

两个破坏开关证明指标不是恒真：

```
--break-history : final_point_hit 1.0 -> 0.2667，checkpoint 1.0 -> 0.4667，rc=1
--break-stale   : forbidden 0 -> 8 次，rc=1
```

pytest 实跑：`python -m pytest tests -q`

```
......................                                                   [100%]
```

## 数据来源（摘要）

30 组多轮对话全部为**虚构合成，无外部来源**；120 篇知识文档复用 EVAL-022 的虚构夹具（未改动）。
生成脚本 `tools/gen_cases.py`（sha256 见 `DATA_PROVENANCE.md`），常量表 + 上游夹具确定性派生，
重跑命令 `python tools/gen_cases.py`。pii 扫描：扫描 143 个文件，命中 0 处。

```
PROVENANCE PASS（15/15）
```