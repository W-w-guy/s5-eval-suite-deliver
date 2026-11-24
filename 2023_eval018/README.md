# 2023 · S5-EVAL-018 文档自动化评测集 doc_auto.contract_fields

到手 $111.38（托管 $148.50，平台抽 25%）。指派来源 `jev_decision`，交付窗口 2026-11-27T13:02Z。

## 一、这个目录里有什么

| 路径 | 用途 |
|---|---|
| `docx2023_deliver.zip` | 完整交付件（121 个文件，1,206,258 B，sha256 `dfa57c51e65aabf5…`），解压后一条命令复跑 |
| `files/**` | **同样内容摊成明文**（116 个文件）——平台复核只读文本、不解 zip，这是给它读的 |
| `files/ACCEPTANCE.md` | 4 条 AC 的四元组对照表：原文 / 判定方式 / 复核命令 / 实际输出原文 |
| `files/DATA_PROVENANCE.md` | 数据来源：生成脚本、种子、重跑命令、产出规模、pii 扫描数与命中数 |
| `files/data/cases.jsonl` | 40 条用例本体，可直接数行 |
| `files/reports/doc_v1.md` · `.png` | 评测报告与「错而未标红」明细截图 |
| `verify_logs/` | Windows 与 Ubuntu 各自实跑的原始日志 |

## 二、工单要求 vs 实际交付

| 工单交付物 | 落在哪 |
|---|---|
| `suite.yaml` | `files/suite_2023.yaml` |
| `cases.jsonl`（40 条：生成 28 + 疑难 12） | `files/data/cases.jsonl`（40 行，`generated:28 / difficult:12`） |
| 40 份合同文件与标准答案 | `files/data/contracts/`（14 text_pdf + 13 scanned_pdf + 13 docx）+ 每条的 `gold`（严格 15 字段） |
| 错字段标红召回计算脚本 | `files/doc_eval/metrics.py`（口径写死：分母=识别错误字段数） |
| 分布统计表 | `files/dist/distribution.csv` + `.md` |
| README | `files/README.md` |

## 三、指标实测（Windows 11 / Py3.11.7 与 Ubuntu 24.04 / Py3.12.3 一致）

```
cases=40 field_acc=0.9900 flag_recall=0.9750 critical_unflagged=0 wrong=6 false_flag=0
```

| 指标 | 实测 | 工单门槛 | 判定 |
|---|---|---|---|
| 字段级准确率 | 0.9900（594/600 字段次） | ≥0.90 | 通过 |
| 错字段标红召回 | 0.9750 | ≥0.95 | 通过 |
| 错而未标红的 critical 字段 | 0 | 0 | 通过 |

两个破坏开关都能让门槛失败，证明指标**可证伪**（不是恒真的 1.0）：

| 开关 | 实测 |
|---|---|
| `--break-flag`（关掉自检标红） | 召回 0.9750→**0.9000**、critical 未标红 0→**3**、rc=1 |
| `--break-accuracy`（解析错日期） | 准确率 0.9900→**0.9750**、召回→**0.7625**、critical 未标红 0→**9**、rc=1 |

## 四、双平台实跑（这是为什么两侧都要跑）

| | Windows 11 / Py3.11.7 | Ubuntu 24.04 / Py3.12.3 |
|---|---|---|
| `verify_2023.py` | 26/26 · rc=0 | 26/26 · rc=0 |
| `pytest tests -q` | 20 passed | 20 passed |
| `eval-lint` | errors=0 | errors=0 |
| `eval-pii-scan` | files=83 unexpected_hits=0 | files=83 unexpected_hits=0 |
| `gen` 同机连跑两次 | 83 文件逐字节相同 | 83 文件逐字节相同 |

**跨平台确定性**（可核对）：
```
data/cases.jsonl   d7f950767758b3ccf8c9d61e16822fcc   ← 两侧完全相同
data/plain (40 份) 3f1d7c2ecd2be2d4fe9e37a0c7317f12   ← 两侧完全相同
```
PDF 的 sha256 两侧**不同**，原因已查清并写进 `README.md` 第五节：Windows 用 simhei、
Ubuntu 用 uming，内嵌子集字体的字节不同。**交付包内是 Windows 侧生成的固定产物，
买家无需重新生成即可直接评分。**

## 五、验收怎么复核（一条命令）

```bash
unzip docx2023_deliver.zip && cd s5-eval-018
pip install pypdf Pillow
python verify_2023.py     # 26 项断言，全绿 rc=0
```

`files/ACCEPTANCE.md` 里每条 AC 都给出了对应的复核命令与本次实际输出原文。
