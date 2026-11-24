# 验收对照表 · S5-EVAL-018 doc_auto.contract_fields

每条验收标准按四元组给出：**原文 / 判定方式 / 复核命令 / 实际输出原文**。
实际输出原文均取自本仓库实跑（Windows 11 / Py3.11.7 与 Ubuntu 24.04 / Py3.12.3 各一遍，日志见 `verify_logs/`）。

复现全部证据只需一条命令：`python verify_2023.py`（26 项断言，全绿 rc=0）。

---

## AC1

**原文**

> cases.jsonl 恰有 40 条（生成 28、疑难 12），eval-lint 与 eval-pii-scan 均通过

**判定方式**

`verify_2023.py` 对 40 条、生成/疑难 28+12、4 版式各 10、3 载体 14/13/13、每份 15 字段、
6 个 critical 字段、12 种疑难类型**逐条硬编码比对**（不是抽样、不是"至少包含"）；
`eval-lint` 逐条校验结构并 rc=0；`eval-pii-scan` 扫 83 个文件、unexpected_hits=0。

**复核命令**

```bash
python verify_2023.py
python tools/eval_lint.py
python tools/eval_pii_scan.py
```

**实际输出原文**

```text
cases.jsonl 恰有 40 条 | 40
生成 28 / 疑难 12 | {'generated': 28, 'difficult': 12}
4 种版式各 10 份 | {'standard': 10, 'two_column': 10, 'table_heavy': 10, 'minimal': 10}
3 种载体 14/13/13 | {'text_pdf': 14, 'scanned_pdf': 13, 'docx': 13}
每份标准答案恰为 15 个字段（多/少均失败） | n=40
critical 字段为含税/不含税金额、甲乙方代码、服务起止日 | ['amount_total', 'amount_ex_tax', 'party_a_code', 'party_b_code', 'service_start', 'service_end']
12 种疑难类型齐全（逐条比对） | 12
40 份文件的格式与 carrier 声明一致（docx 真 OOXML / pdf 真 PDF / 扫描件无文字层） | []
eval-lint 通过（rc=0） | eval-lint: cases=40 layouts=4 carriers=3 errors=0 warnings=0
eval-pii-scan 通过（unexpected_hits=0） | eval-pii-scan: files=83 unexpected_hits=0 exempt_999999=432 pdf_without_textlayer=13（其正文以 data/plain 同源文本被扫描）
```

---

## AC2

**原文**

> 标红召回脚本对 3 组手工构造的结果计算正确（单元测试通过）

**判定方式**

`verify_2023.py` 里用同一份 gold 构造 3 组预测：全部错字段标红=1.0、只标一半=0.5、
一个都不标=0.0；并断言分母口径=识别错误字段数、误报单独计数不进分母、空集按约定记 1.0。
另有 `python -m pytest tests -q` 的 20 个用例覆盖同样的手算。

**复核命令**

```bash
python verify_2023.py
python -m pytest tests -q
```

**实际输出原文**

```text
标红召回 3 组手工构造：全标红=1.0 / 半标红=0.5 / 全不标红=0.0 | [1.0, 0.5, 0.0]
召回的分子分母口径写死：分母=识别错误字段数 | wrong_total=2 recall=0.5
识别正确却被标红单独计数、不进召回分母 | right_but_flagged=[]
无识别错误时召回按显式约定记 1.0 | 1.0
单元测试全部通过 | ....................                                                     [100%]
```

---

## AC3

**原文**

> 报告中单列「错而未标红」明细（用 mock 输出生成的报告截图）

**判定方式**

`python -m doc_eval --tag verify` 生成 `reports/doc_verify.md`（含「错而未标红明细」小节、
15 个字段准确率、按版式/载体分组、判定）与 `reports/doc_verify.json`；
`python tools/make_screenshot.py verify` 把同一份 json 的指标与明细渲染成 PNG（非手绘），
`verify_2023.py` 断言 PNG 存在、>20KB、且像素方差与暗像素数达标（非空白图）。

**复核命令**

```bash
python -m doc_eval --tag verify
python tools/make_screenshot.py verify
python verify_2023.py
```

**实际输出原文**

```text
runner 跑通且指标达标（rc=0） | cases=40 field_acc=0.9900 flag_recall=0.9750 critical_unflagged=0 wrong=6 false_flag=0
报告单列「错而未标红明细」小节 | reports/doc_verify.md
报告中「错而未标红的 critical 字段数」= 0 | 0
报告按字段输出准确率 | 15 个字段行
报告截图由 mock 输出渲染、非空白 | 83495 bytes
截图对应 reports/doc_verify.json（同一 tag 同一批输出） | tag=verify
```

---

## AC4

**原文**

> 全部信用代码第 3–8 位为 999999（脚本检查输出）

**判定方式**

`verify_2023.py` 遍历 40 份 × 甲乙方 = 80 个代码，断言全部 18 位、
第 3–8 位为 `999999`、字符集 `[0-9A-Z]`，并打印命中的区划码集合（应为单元素 `['999999']`）；
`tools/eval_lint.py` 内做同样校验作为第二道独立检查（rc=0）。

**复核命令**

```bash
python verify_2023.py
python tools/eval_lint.py
```

**实际输出原文**

```text
全部 80 个信用代码第 3-8 位为 999999 | n=80 命中区划码=['999999']
信用代码均为 18 位且字符集合法 | []
脚本检查输出可复核（eval-lint 内同样校验代码格式，rc=0） | eval-lint: cases=40 layouts=4 carriers=3 errors=0 warnings=0
```

---

## 附：指标可证伪性（不属于 AC，但证明上面的数字不是恒真）

| 开关 | 实测输出 |
|---|---|
| `破坏 --break-flag 打掉自检后 critical 未标红 > 0 且 rc=1` | `cases=40 field_acc=0.9900 flag_recall=0.9000 critical_unflagged=3 wrong=6 false_flag=0` |
| `破坏 --break-accuracy 让日期解析错后 rc=1` | `cases=40 field_acc=0.9750 flag_recall=0.7625 critical_unflagged=9 wrong=15 false_flag=0` |

两个开关都让 rc=1，说明指标确实测得出问题，不是写死的 1.0。
