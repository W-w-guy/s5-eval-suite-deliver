# CROSS_PLATFORM — 双平台实跑与产物一致性

同一份交付包在两个平台的**全新解压目录**里各跑一遍，记录原始输出，并逐文件比对产物哈希。

## 环境

| 平台 | 版本 | 依赖 |
| --- | --- | --- |
| Windows 11 | Python 3.11.7 / pytest 9.1.1 | 仅标准库（YAML 用自写解析器） |
| Ubuntu 24.04（Linux 7.0.0-38-generic） | Python 3.12.3 / pytest 7.4.4 | 仅标准库 |

## 五个入口的结果（两侧全部 rc=0）

| 入口 | Windows | Ubuntu |
| --- | --- | --- |
| `python tools/verify.py` | SUMMARY 43/43 PASS | SUMMARY 43/43 PASS |
| `python -m pytest tests -v` | 50 passed | 50 passed |
| `python tools/mutate.py` | CAUGHT 13 / MISSED 0 / INVALID 0 | 同左 |
| `python tools/pii_scan.py` | scanned=28 hits=0 | scanned=28 hits=0 |
| `python tools/build_docs.py` | verify_rc=0，回填后复扫一致 | 同左 |

## 校验和

- 解压后 `sha256sum -c SHA256SUMS.txt`：**29 条全 OK、0 条 FAILED**；
- 按 README 顺序跑完全部入口之后再校验：**仍是 0 条不一致**（engine.py 与 build_docs.py 均幂等）；
- `verify_logs/` 为实跑日志快照，随运行变化，**不纳入 SHA256SUMS**。

## 产物逐字节比对

| 文件 | Windows sha256 前 16 位 | Ubuntu 前 16 位 | 一致 |
| --- | --- | --- | --- |
| `data/suite.yaml` | `52960533d7b6cf32` | `52960533d7b6cf32` | 是 |
| `data/runs/BASE_V1.json` | `f02741d35d5aa998` | `f02741d35d5aa998` | 是 |
| `data/runs/CUR_FLAKY.json` | `2bc37d1081178556` | `2bc37d1081178556` | 是 |
| `data/baselines/kb_qa.yaml` | `c4bfbb443a79631e` | `c4bfbb443a79631e` | 是 |
| `pkg/baseline.py` | `25f1fd6147fe4454` | `25f1fd6147fe4454` | 是 |
| `pkg/cmd.py` | `538843d215e07622` | `538843d215e07622` | 是 |
| `pkg/engine.py` | `a819a2967ce11581` | `a819a2967ce11581` | 是 |
| `README.md` | `73d36fa1cb6956f4` | `73d36fa1cb6956f4` | 是 |
| `ACCEPTANCE.md` | `816d1c41e79be5c7` | `816d1c41e79be5c7` | 是 |
| `DATA_PROVENANCE.md` | `697d3a7339b7748e` | `697d3a7339b7748e` | 是 |

这 10 个文件两侧**逐字节相同**。原因：文本一律以 `newline="\n"` 写出；9 个运行场景由下标确定性生成，无随机数；must 要点是否跟随 passed 也由下标取模决定；日期全部是显式常量，本包不读系统时间、不依赖 tzdata。

## 原始日志（本目录内）

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `WINDOWS_20261127.log` | 10,833 | `5a9c4aa5cec2b262…` |
| `UBUNTU_20261127.log` | 10,830 | `6ace43f330b28fc2…` |

## 复核方式

1. 两份日志首行是环境标记，**首行之后全部内容为该平台 `tools/*.py` 与 `pytest` 的原始 stdout/stderr，未经修改**。
2. 判据不依赖日志本身：两侧全新目录按 README 顺序跑完全部入口后**再**执行 `sha256sum -c SHA256SUMS.txt`，均为 0 条不一致。
3. 日志字节数差异来自 pytest 汇总行的耗时数字（`50 passed in 2.03s` vs `1.05s`）与路径分隔符，其余逐行相同。
