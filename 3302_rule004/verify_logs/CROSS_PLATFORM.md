# 跨平台一致性核对（Windows ↔ Ubuntu）

同一份 `dis3302.zip` 分别解压到两个全新空目录，逐条执行同样 5 个入口，再比对产物 sha256。

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
| `tools/verify.py` | rc=0，SUMMARY 20/20 PASS | rc=0，SUMMARY 20/20 PASS |
| `pytest tests` | rc=0，13 passed | rc=0，13 passed |
| `tools/mutate.py` | rc=0，MUTATION PASS（7/7 被抓到） | rc=0，MUTATION PASS（7/7 被抓到） |
| `tools/pii_scan.py` | rc=0，scanned=29 hits=0 | rc=0，scanned=29 hits=0 |

## 产物逐字节一致

| 文件 | Windows sha256 | Ubuntu sha256 | 一致 |
| --- | --- | --- | --- |
| `docs/boundary_rules.csv` | `f005b805e2dceb80…` | `f005b805e2dceb80…` | ✅ |
| `docs/coverage.csv` | `d2735e91835dc3ab…` | `d2735e91835dc3ab…` | ✅ |
| `docs/discount_expected.csv` | `28362018bda9194a…` | `28362018bda9194a…` | ✅ |
| `docs/discount_routing.md` | `cbb0efe2de7c0ae3…` | `cbb0efe2de7c0ae3…` | ✅ |
| `docs/discount_routing.xlsx` | `6d37784191c2508c…` | `6d37784191c2508c…` | ✅ |

`SHA256SUMS.txt` 两侧同为 `05947b095a4383eef6eb8554ba9e7857adccf668c4147890041750db22b16779`；
`python tools/gen.py` 重跑一次后 docs 五个文件哈希不变（幂等）。

## 日志差异只有 pytest 汇总行

`verify / gen / mutate / pii` 四份日志两侧去掉换行差异后逐字节相同。
`pytest` 侧 Windows 用 `--tb=short -p no:cacheprovider` 才输出 `13 passed` 汇总行（pytest 9 的 `-q` 只打进度点），Ubuntu 用 `-q` 即输出；用例数与结论两侧一致（13 passed）。

日志原文见 `verify_logs/WINDOWS_20261124.log` 与 `verify_logs/UBUNTU_20261124.log`。
