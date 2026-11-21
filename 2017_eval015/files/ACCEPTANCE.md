# 验收对应表（ACCEPTANCE）—— #2017 S5-EVAL-015

本文件逐条回答四条验收标准：**判定方式 / 复核命令 / 实际输出原文**。

平台复核只读文本、不执行代码（`runtime_verified: false`），所以这里贴的是**真跑出来的输出原文**。
所有命令可在解压后的包根目录直接重跑（Python 3.11+，零第三方运行时依赖）。

---
## AC1　cases.jsonl has exactly 30 entries (12 outlines, 18 summaries); both eval-lint and eval-pi

**判定方式**：数 `data/cases.jsonl` 条目并统计 12/18 分布；`eval-lint` 校验字段与分布；`eval-pii-scan` 扫手机号/邮箱/身份证。

**复核命令**：`python verify_2017.py`

**实际输出原文**：

```
[ OK ] AC1 cases.jsonl 恰 30 条 | 30
[ OK ] AC1 分布 提纲 12 / 摘要 18 | {'summary': 18, 'outline': 12}
[ OK ] AC1 提纲用例含嘉宾资料与访谈主题 
[ OK ] AC1 提纲用例声明不谈话题 
[ OK ] AC1 摘要用例指向真实存在的转写稿文件 
[ OK ] AC1 摘要用例带 3 条金标金句 
[ OK ] AC1 每条都写明 forbidden_points 
[ OK ] AC1 eval-pii-scan 通过（转写稿无手机号/邮箱） | ([], [])
[ OK ] AC1 eval-lint 通过（结构与字段齐全） 
```

---
## AC2　The verbatim quote check and timestamp monotonicity check correctly judge positive and neg

**判定方式**：两类检查各自准备正反夹具：合法逐字引用 → 通过；改写/编造引用 → 失败。时间戳检查同样要用非单调夹具证明会失败。

**复核命令**：`python verify_2017.py`

**实际输出原文**：

```
[ OK ] AC2 金句：正夹具判通过 
[ OK ] AC2 金句：反夹具（改一个字）判失败 
[ OK ] AC2 时间戳：正夹具判通过 
[ OK ] AC2 时间戳：反夹具（乱序）判失败 
[ OK ] AC2 时间戳：反夹具（超总时长）判失败 
[ OK ] AC2 有单元测试且正反夹具都覆盖 
```

---
## AC3　All 18 transcripts have character counts between 3,000–6,000 (statistics output)

**判定方式**：逐份统计 `data/transcripts/IP-S*.txt` 字符数，全部落在 [3000, 6000] 区间。

**复核命令**：`python verify_2017.py`

**实际输出原文**：

```
[ OK ] AC3 18 份转写稿字数全部在 3000–6000 | 3159..5577
[ OK ] AC3 字数分布覆盖整个区间（max-min > 1500） | 2418
[ OK ] AC3 统计输出与实际文件长度一致 
```

---
## AC4　Ran eval-run successfully using echo mock and generated the report

**判定方式**：`python -m ip_eval` 用 echo mock 跑通，退出码 0，生成 Markdown/JSON 报告。

**复核命令**：`python verify_2017.py`

**实际输出原文**：

```
[ OK ] AC4 echo mock 跑通 eval-run（rc=0） | rc=0
[ OK ] AC4 生成 Markdown 报告 
[ OK ] AC4 报告含三项检查列（金句/时间戳/数字） 
[ OK ] AC4 报告含未通过明细小节 
[ OK ] AC4 全部 30 条通过（提纲与摘要均 100%） | 1.0000
```

---
## 汇总

```
TOTAL 30, PASS 30, FAIL 0
```

pytest 实跑：`python -m pytest tests -q`

```
..............................                                           [100%]
```

## 数据来源（摘要）

30 条用例与 18 份转写稿全部为**虚构合成，无外部来源**。生成脚本 `tools/gen_cases.py`
（sha256 见 `DATA_PROVENANCE.md`），种子 `random.Random(2017)` 写死，重跑命令 `python tools/gen_cases.py`。
pii 扫描：扫描 51 个文件，命中 0 处。

```
PROVENANCE PASS（15/15）
```