# 跨平台一致性核对（Windows ↔ Ubuntu）

同一份 `cs3322.zip` 分别解压到两个全新空目录，逐条执行同样 5 个入口，再比对产物 sha256。

## 环境

| | Windows | Ubuntu |
| --- | --- | --- |
| 系统 | Windows 11 | Ubuntu 24.04.5 LTS（内核 7.0.0-38） |
| Python | 3.11.7 | 3.12.3 |
| pytest | 9.1.1 | 7.4.4 |
| openpyxl | 3.x | 3.1.5 |

## 五项入口退出码

| 入口 | Windows | Ubuntu |
| --- | --- | --- |
| `tools/gen.py` | rc=0 | rc=0 |
| `tools/verify.py` | rc=0，SUMMARY 23/23 PASS | rc=0，SUMMARY 23/23 PASS |
| `pytest tests` | rc=0，9 passed | rc=0，9 passed |
| `tools/mutate.py` | rc=0，MUTATION PASS（7/7 被抓到） | rc=0，MUTATION PASS（7/7 被抓到） |
| `tools/pii_scan.py` | rc=0，scanned=31 hits=0 | rc=0，scanned=31 hits=0 |

## 产物逐字节一致

| 文件 | Windows sha256 | Ubuntu sha256 | 一致 |
| --- | --- | --- | --- |
| `docs/coverage.csv` | `8a50d3bbe606040b…` | `8a50d3bbe606040b…` | ✅ |
| `docs/cs_expected.csv` | `96e50839d2fa4bfe…` | `96e50839d2fa4bfe…` | ✅ |
| `docs/cs_transfer_sop.md` | `91f6ea452ca7a708…` | `91f6ea452ca7a708…` | ✅ |
| `docs/knowledge_gap.md` | `087b76586b20afc5…` | `087b76586b20afc5…` | ✅ |
| `docs/transfer_flow.md` | `199b835ff458b853…` | `199b835ff458b853…` | ✅ |
| `docs/transfer_rules.csv` | `0b918129ecf8a7fd…` | `0b918129ecf8a7fd…` | ✅ |
| `docs/transfer_tables.xlsx` | `3775ccbff36db7d5…` | `3775ccbff36db7d5…` | ✅ |

`SHA256SUMS.txt` 两侧同为 `b47b8ae33c879acebc2f802f5cebfd433396163b7bd75762bc9279ac2afa41cd`；`python tools/gen.py` 重跑一次后 docs 七个文件哈希不变（幂等）。

## 日志差异只有 pytest 计时行

`gen / verify / mutate / pii` 四份日志两侧去换行差异后逐字节相同；`pytest` 只差耗时（0.18s vs 0.02s），用例数与结论一致（9 passed）。

日志原文见 `verify_logs/WINDOWS_20261124.log` 与 `verify_logs/UBUNTU_20261124.log`。
