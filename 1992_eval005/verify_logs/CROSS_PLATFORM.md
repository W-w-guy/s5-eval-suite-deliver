# CROSS_PLATFORM — 双平台实跑与产物一致性

同一份交付包在两个平台的**全新解压目录**里各跑一遍，记录原始输出，并逐文件比对产物哈希。

## 环境

| 平台 | 版本 | 依赖 |
| --- | --- | --- |
| Windows 11 | Python 3.11.7 / pytest 9.1.1 | 标准库 + PyYAML 6.0.3（可选） |
| Ubuntu 24.04（Linux 7.0.0-38-generic） | Python 3.12.3 / pytest 7.4.4 | 标准库 + PyYAML 6.0.2 |

## 六个入口的结果（两侧全部 rc=0）

| 入口 | Windows | Ubuntu |
| --- | --- | --- |
| `python tools/gen.py` | WROTE cases=34 handcalc_rows=306 | 同左 |
| `python tools/verify.py` | SUMMARY 20/20 PASS | SUMMARY 20/20 PASS |
| `python -m pytest tests -v` | 68 passed | 68 passed |
| `python tools/mutate.py` | CAUGHT 11 / MISSED 0 / INVALID 0 | 同左 |
| `python tools/pii_scan.py` | scanned=55 hits=0 | scanned=55 hits=0 |
| `python tools/build_docs.py` | verify_rc=0，回填后复扫一致 | 同左 |

## 校验和

- 解压后 `sha256sum -c SHA256SUMS.txt`：**55 条全 OK、0 条 FAILED**；
- 按 README 顺序跑完六个入口之后再校验：**仍是 0 条不一致**（gen.py 与 build_docs.py 均幂等）；
- `verify_logs/` 为实跑日志快照，随运行变化，**不纳入 SHA256SUMS**。

## 产物逐字节比对

| 文件 | Windows sha256 前 16 位 | Ubuntu 前 16 位 | 一致 |
| --- | --- | --- | --- |
| `data/cases.jsonl` | `28d16b1cf236dba8` | `28d16b1cf236dba8` | 是 |
| `data/handcalc.csv` | `942d335e1fb89cc9` | `942d335e1fb89cc9` | 是 |
| `data/suite.yaml` | `3d4f4ee7526e20e5` | `3d4f4ee7526e20e5` | 是 |
| `data/field_schema.json` | `ae57a2d2b4908a48` | `ae57a2d2b4908a48` | 是 |
| `README.md` | `5e8c4833ac32b733` | `5e8c4833ac32b733` | 是 |
| `ACCEPTANCE.md` | `a7a1cb4a2ac0fae0` | `a7a1cb4a2ac0fae0` | 是 |
| `DATA_PROVENANCE.md` | `a3f37328bd93d422` | `a3f37328bd93d422` | 是 |
| `pkg/scorer.py` | `d19e3953b470534d` | `d19e3953b470534d` | 是 |
| `pkg/normalize.py` | `6cd1c77fdeb96095` | `6cd1c77fdeb96095` | 是 |
| `pkg/engine.py` | `e7c1983c6a8f91f6` | `e7c1983c6a8f91f6` | 是 |

这 10 个文件两侧**逐字节相同**。原因：文本一律以 `newline="\n"` 写出；所有数值、日期、信用代码为手写固定常量，无随机数；时间不读系统 tzdata（Windows 无 tzdata，本包不使用任何时区）。

## 原始日志（本目录内）

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `WINDOWS_20261127.log` | 11,715 | `ccf5515dd8a35feb9f95a83687f68361e31a4fcfd161816fb5e5ae3bd9a882b4` |
| `UBUNTU_20261127.log` | 11,403 | `62510a517245abbc8d9d6a35d2ce6d37d55f2a1d8ad288728e81c136c6392d7a` |

## 复核方式

1. 两份日志首行是环境标记，**首行之后全部内容为该平台 `tools/*.py` 与 `pytest` 的原始 stdout/stderr，未经修改**。
2. 判据不依赖日志本身：两侧全新目录按 README 顺序跑完六个入口后**再**执行 `sha256sum -c SHA256SUMS.txt`，均为 0 条不一致。
3. 日志字节数差异来自 pytest 汇总行的耗时数字（`68 passed in 0.46s` vs `0.28s`）与路径分隔符，其余逐行相同。
