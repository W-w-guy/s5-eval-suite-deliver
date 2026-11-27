# CROSS_PLATFORM — 双平台实跑与产物一致性

同一份交付包（本 zip）在两个平台的**全新解压目录**里各跑一遍，记录原始输出，并逐文件比对产物哈希。

## 环境

| 平台 | 版本 | 依赖 |
| --- | --- | --- |
| Windows 11 | Python 3.11.7 | 标准库 + openpyxl 3.1.5 |
| Ubuntu 24.04（Linux 7.0.0-38-generic） | Python 3.12.3 / pytest 7.4.4 | 标准库 + openpyxl 3.1.5 |

## 六个入口的结果（两侧全部 rc=0）

| 入口 | Windows | Ubuntu |
| --- | --- | --- |
| `python tools/gen.py` | 产出 8 个文件（幂等） | 产出 8 个文件（幂等） |
| `python tools/verify.py` | SUMMARY 23/23 PASS | SUMMARY 23/23 PASS |
| `python -m pytest tests -v` | 9 passed | 9 passed |
| `python tools/mutate.py` | MUTATION PASS（7/7 被抓到） | MUTATION PASS（7/7 被抓到） |
| `python tools/pii_scan.py` | scanned=34 hits=0 | scanned=34 hits=0 |
| `python tools/build_docs.py` | verify_rc=0，回填后复扫一致 | verify_rc=0，回填后复扫一致 |

## 校验和

- 解压后 `sha256sum -c SHA256SUMS.txt`：**37 条全 OK、0 条不一致**；
- 按 README 顺序跑完 `gen → verify → pytest → mutate → pii_scan → build_docs` 之后**再**校验：仍是 **0 条不一致**（两侧都验证过）——`gen.py` 与 `build_docs.py` 均幂等，重跑不改字节；
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

这 7 个文件都由 `tools/gen.py` 从引擎重算生成，两侧**逐字节相同**。原因：文本一律以 `newline="\n"` 写出；时间推算用纯 naive datetime、不读系统 tzdata（Windows 无 tzdata，`zoneinfo.ZoneInfo("Asia/Shanghai")` 会直接抛 ZoneInfoNotFoundError）。

## 原始日志（本目录内）

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `verify_logs/WINDOWS_20261127.log` | 4,716 | `2637592b2351c4f613c0cf29770614b5a6f7550a8df7387cd2a05b11928fc61d` |
| `verify_logs/UBUNTU_20261127.log` | 5,035 | `014d7a72102bfe31ebe3892a8f7a29085c26722b89851ce803d6c412612fafbb` |

## 本文件的复核方式

1. 两份日志的**首行是环境标记**（`=== Windows 3.11.7 / 全新解压目录 ===`、`=== Ubuntu 3.12.3 / 全新解压目录 ===`），由采集脚本写入；**首行之后全部内容均为该平台 `tools/*.py` 与 `pytest` 的原始 stdout/stderr，未经修改**。
2. 判据不依赖日志本身：在两侧全新目录按 README 顺序跑完六个入口后**再**执行 `sha256sum -c SHA256SUMS.txt`，两侧均为 0 条不一致。
3. 重跑与日志的差异只有 pytest 汇总行的耗时数字（`9 passed in 0.24s` 这类）与路径分隔符，其余逐行相同 —— 已实测归一化比对确认。
