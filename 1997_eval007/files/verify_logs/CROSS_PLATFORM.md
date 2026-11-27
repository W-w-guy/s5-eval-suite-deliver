# CROSS_PLATFORM — 双平台实跑与产物一致性

同一份交付包在两个平台的**全新解压目录**里各跑一遍，记录原始输出，并逐文件比对产物哈希。

## 环境

| 平台 | 版本 | 依赖 |
| --- | --- | --- |
| Windows 11 | Python 3.11.7 / pytest 9.1.1 | 仅标准库 |
| Ubuntu 24.04（Linux 7.0.0-38-generic） | Python 3.12.3 / pytest 7.4.4 | 仅标准库 |

## 三个入口的结果（两侧全部 rc=0）

| 入口 | Windows | Ubuntu |
| --- | --- | --- |
| `python tools/verify.py` | SUMMARY 31/31 PASS | SUMMARY 31/31 PASS |
| `python -m pytest tests -v` | 60 passed | 60 passed |
| `python tools/mutate.py` | CAUGHT 14 / MISSED 0 / INVALID 0 | 同左 |

## 校验和

- 解压后 `sha256sum -c SHA256SUMS.txt`：**50 条全 OK、0 条 FAILED**；
- 按 README 顺序跑完 verify / pytest / mutate / build_docs 之后再校验：**0 条不一致**；
- 再重复跑一次 `build_docs.py`：**仍 0 条不一致**（幂等）；
- `verify_logs/` 与 `docs/perf.json` 是运行产物，**不纳入 SHA256SUMS**。

## 产物逐字节比对

| 文件 | Windows sha256 前 16 位 | Ubuntu 前 16 位 | 一致 |
| --- | --- | --- | --- |
| `pkg/detect.py` | `f6e8ae7a56287e29` | `f6e8ae7a56287e29` | 是 |
| `pkg/checksum.py` | `ce63a497198998f7` | `ce63a497198998f7` | 是 |
| `pkg/rules.py` | `aa94a362afca69c5` | `aa94a362afca69c5` | 是 |
| `pkg/scanner.py` | `d75f90402ad4638c` | `d75f90402ad4638c` | 是 |
| `pkg/cmd.py` | `6f4873dc23d04f06` | `6f4873dc23d04f06` | 是 |
| `pkg/engine.py` | `78dab88255e2fb96` | `78dab88255e2fb96` | 是 |
| `data/fixtures/cases.json` | `508ed0251e6e5614` | `508ed0251e6e5614` | 是 |
| `data/perf1000/cases_1000.jsonl` | `c68f922a8dfdf756` | `c68f922a8dfdf756` | 是 |
| `README.md` | `1f2db6558b9c0168` | `1f2db6558b9c0168` | 是 |
| `ACCEPTANCE.md` | `0de3aa86a263acff` | `0de3aa86a263acff` | 是 |
| `DATA_PROVENANCE.md` | `8b2b66398f7b852f` | `8b2b66398f7b852f` | 是 |

这 11 个文件两侧**逐字节相同**。原因：文本一律以 `newline="\n"` 写出；全部夹具为手写常量，号码由校验位算法从自选号段补出；1000 条性能用例按序号确定性生成；不读系统时间、不依赖 tzdata。

## 本轮踩到的一个真缺陷（已修）

首版把性能耗时写进了 `verify.py` 的断言输出（`冷启动 56.8 ms` 这类），而 `ACCEPTANCE.md` 是由 verify 输出生成的 —— 于是每次 `build_docs.py` 产出的字节都不同，买家跑完全套再 `sha256sum -c` 必然报 `ACCEPTANCE.md` 不一致（Ubuntu 侧首次实测就撞上）。
修法：**耗时数值不进断言输出**，只断言「未超预算」；具体毫秒数落到 `docs/perf.json`，那是不进校验和的运行产物。判据：凡是每次运行都变的数值，都不能流进被校验和覆盖的文件。

## 原始日志（本目录内）

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `WINDOWS_20261127.log` | 10,542 | `5a89b8fbd5f71f91c2992fc3678ee6b1e6d8f4077fa063820dbf00691d068567` |
| `UBUNTU_20261127.log` | 10,540 | `215c759fa901a7628e42396a11f7fcdadfdd92e4c92571cd266cfe80a4c87bff` |

## 复核方式

1. 两份日志首行是环境标记，**首行之后全部内容为该平台 `tools/*.py` 与 `pytest` 的原始 stdout/stderr，未经修改**。
2. 逐行比对结果：除环境标记行与 pytest 的 `test session starts` / `passed in X s` 装饰行外，两侧完全一致。
3. 判据不依赖日志本身：两侧全新目录跑完全部入口后**再**执行 `sha256sum -c SHA256SUMS.txt`，均为 0 条不一致。
