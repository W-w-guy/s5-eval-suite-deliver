# CROSS_PLATFORM — 双平台实跑与产物一致性

同一份交付包在两个平台的**全新解压目录**里各跑一遍，记录原始输出，并逐文件比对产物哈希。

## 环境

| 平台 | 版本 | 依赖 |
| --- | --- | --- |
| Windows 11 | Python 3.11.7 / pytest 9.1.1 | 仅标准库（YAML 用自写解析器） |
| Ubuntu 24.04（Linux 7.0.0-38-generic） | Python 3.12.3 / pytest 7.4.4 | 仅标准库 |

## 六个入口的结果（两侧全部 rc=0）

| 入口 | Windows | Ubuntu |
| --- | --- | --- |
| `python pkg/engine.py` | WROTE runs=6 cases=924 | 同左 |
| `python tools/verify.py` | SUMMARY 29/29 PASS | SUMMARY 29/29 PASS |
| `python -m pytest tests -v` | 80 passed | 80 passed |
| `python tools/mutate.py` | CAUGHT 11 / MISSED 0 / INVALID 0 | 同左 |
| `python tools/pii_scan.py` | scanned=31 hits=0 | scanned=31 hits=0 |
| `python tools/build_docs.py` | verify_rc=0，回填后复扫一致 | 同左 |

## 校验和

- 解压后 `sha256sum -c SHA256SUMS.txt`：**32 条全 OK、0 条 FAILED**；
- 按 README 顺序跑完全部入口之后再校验：**仍是 0 条不一致**（engine.py 与 build_docs.py 均幂等）；
- `verify_logs/` 为实跑日志快照，随运行变化，**不纳入 SHA256SUMS**。

## 产物逐字节比对

| 文件 | Windows sha256 前 16 位 | Ubuntu 前 16 位 | 一致 |
| --- | --- | --- | --- |
| `data/guardrail_policy.yaml` | `90afc1e67d660081` | `90afc1e67d660081` | 是 |
| `data/runs/RUN_OK.json` | `abccd5f1a9e54f2b` | `abccd5f1a9e54f2b` | 是 |
| `data/runs/RUN_P2_ROUND.json` | `a65aadab754db4b7` | `a65aadab754db4b7` | 是 |
| `data/waivers/waivers_ok.yaml` | `dec4dcac993e0a49` | `dec4dcac993e0a49` | 是 |
| `pkg/gate.py` | `35292ce89ada39c7` | `35292ce89ada39c7` | 是 |
| `pkg/policy.py` | `8c2c41bdc5d903c0` | `8c2c41bdc5d903c0` | 是 |
| `pkg/clock.py` | `6c8b02dbe3dae0a5` | `6c8b02dbe3dae0a5` | 是 |
| `README.md` | `3671152677cd2e35` | `3671152677cd2e35` | 是 |
| `ACCEPTANCE.md` | `4c7a67f351e70486` | `4c7a67f351e70486` | 是 |
| `DATA_PROVENANCE.md` | `6ee3ed804534e1d2` | `6ee3ed804534e1d2` | 是 |

这 10 个文件两侧**逐字节相同**。原因：文本一律以 `newline="\n"` 写出；6 个运行场景由下标确定性生成，无随机数；日期全部是显式常量，`pkg/clock.py` 不 import datetime、不读系统时间。

## 原始日志（本目录内）

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `WINDOWS_20261127.log` | 11,288 | `e0672bc0c5da6c334300ce78398a5884708ed4e96932b4bd0c1fd7449c0cde42` |
| `UBUNTU_20261127.log` | 11,326 | `42b497cadbe896ba04b961cf75a2d0ce4385a6f930d282a7246fc05476ac2a5d` |

## 复核方式

1. 两份日志首行是环境标记，**首行之后全部内容为该平台 `tools/*.py` 与 `pytest` 的原始 stdout/stderr，未经修改**。
2. 判据不依赖日志本身：两侧全新目录按 README 顺序跑完全部入口后**再**执行 `sha256sum -c SHA256SUMS.txt`，均为 0 条不一致。
3. 日志字节数差异来自 pytest 汇总行的耗时数字（`80 passed in 0.51s` vs `0.33s`）与路径分隔符，其余逐行相同。

## 本轮踩到的一个真缺陷（已修）

首版把 `SHA256SUMS.txt` 也纳入 PII 扫描范围，导致 `DATA_PROVENANCE.md` 里记的 `scanned=` 数在打包前后不同（打包前 31、打包后 32，因为包里多了一份校验和文件），于是买家跑完 `build_docs.py` 再 `sha256sum -c` 会报 `DATA_PROVENANCE.md` 不一致。修法是在 `pii_scan.py` 里把 `SHA256SUMS.txt` 加入 `SKIP_FILES` —— 这类自指循环必须靠「解压到全新目录、跑完全套、再校验」才能发现，本地打包目录里自查是看不出来的。
