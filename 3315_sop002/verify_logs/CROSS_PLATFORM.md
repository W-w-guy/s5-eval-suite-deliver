# CROSS_PLATFORM — 双平台实跑与产物一致性

同一份交付包（本 zip）在两个平台的**全新解压目录**里各跑一遍，记录原始输出，并逐文件比对产物哈希。

## 环境

| 平台 | 版本 | 依赖 |
| --- | --- | --- |
| Windows 11 | Python 3.11.7 | 标准库 + openpyxl 3.1.5 |
| Ubuntu 24.04（Linux 7.0.0-38-generic） | Python 3.12.3 / pytest 7.4.4 | 标准库 + openpyxl 3.1.5 |

## 五个入口的结果（两侧全部通过）

| 入口 | Windows | Ubuntu |
| --- | --- | --- |
| `python tools/gen.py` | rc=0，产出 8 个文件 | rc=0，产出 8 个文件 |
| `python tools/verify.py` | SUMMARY 23/23 PASS | SUMMARY 23/23 PASS |
| `python -m pytest tests -v` | 9 passed | 9 passed |
| `python tools/mutate.py` | MUTATION PASS（7/7 被抓到） | MUTATION PASS（7/7 被抓到） |
| `python tools/pii_scan.py` | scanned=35 hits=0 | scanned=35 hits=0 |

## 校验和

- 解压后 `sha256sum -c SHA256SUMS.txt`：**全部 OK，0 条 FAILED**；
- 在 Ubuntu 上重跑 `python tools/gen.py` 后**再**校验：**0 条不一致**（产物幂等，重跑不改字节）；
- `docs/join_tables.xlsx` 为 openpyxl 写出的 zip 容器（内部条目带本地时间与 create_system），**不纳入 SHA256SUMS**；跨平台一致性改比单元格值，见 `docs/join_expected.csv` 与 `tests/test_examples.py` 中的逐格断言。

## 文档产物逐字节比对

| 文件 | Windows sha256 前 16 位 | Ubuntu sha256 前 16 位 | 一致 |
| --- | --- | --- | --- |
| `docs/join_sop.md` | `ebc23ab8130b2ff5` | `ebc23ab8130b2ff5` | 是 |
| `docs/welcome_scripts.csv` | `502376059447e550` | `502376059447e550` | 是 |
| `docs/materials.csv` | `0f43736699cc7e21` | `0f43736699cc7e21` | 是 |
| `docs/checklists.md` | `9d20d35027aa0138` | `9d20d35027aa0138` | 是 |
| `docs/card_questions.md` | `bf541b658ea7c69e` | `bf541b658ea7c69e` | 是 |
| `docs/join_expected.csv` | `42ba06ccac89d629` | `42ba06ccac89d629` | 是 |
| `docs/coverage.csv` | `a1c47c748c60f44f` | `a1c47c748c60f44f` | 是 |

这 7 个文件都由 `tools/gen.py` 从引擎重算生成，两侧**逐字节相同**。原因：文本一律以 `newline="\n"` 写出，时间推算用纯 naive datetime、不读系统 tzdata（Windows 无 tzdata，`zoneinfo.ZoneInfo("Asia/Shanghai")` 会直接抛 ZoneInfoNotFoundError）。

## 原始日志（本目录内）

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `verify_logs/WINDOWS_20261127.log` | 3,955 | `5ccda582e1277ad51bfd4f3dfd5f3ef47fa75b510e45af6bdcb583b40ee1fdfd` |
| `verify_logs/UBUNTU_20261127.log` | 4,607 | `af3bd9fc7c9fc9d5c65cc1b3b635d3964dc570d0f5af32b6eb45f897e002ce7b` |

两份日志字节数不同，原因是平台间差异：① pytest 汇总行的耗时数字不同（`9 passed in 0.56s` vs `0.20s`）；② 路径分隔符不同（Windows 侧出现反斜杠路径行）。除此之外逐行相同，**不是内容不一致**。判定以退出码、SUMMARY 行与逐文件 sha256 为准。

## 本文件的复核方式

1. 两份日志的**首行是环境标记**（`=== Windows 3.11.7 / 全新解压目录 ===`、`=== Ubuntu 3.12.3 / 全新解压目录 ===`），由采集脚本写入；**首行之后的全部内容均为该平台 `tools/*.py` 与 `pytest` 的原始 stdout/stderr，未经任何修改或删改**。
2. 判据不依赖日志本身：在两侧全新目录里按 README 顺序跑完 `gen → verify → pytest → mutate → pii_scan → build_docs` 之后，**再**执行 `sha256sum -c SHA256SUMS.txt`，两侧结果均为 **39 条全 OK、0 条不一致**（`gen.py` 与 `build_docs.py` 均幂等，重跑不改字节）。
3. 重跑与日志的差异只有 pytest 汇总行里的耗时数字（`9 passed in 0.20s` / `0.61s` 这类），其余逐行相同 —— 已实测比对：归一化耗时后除环境标记行外**完全一致**。
