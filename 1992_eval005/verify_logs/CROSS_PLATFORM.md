# CROSS_PLATFORM — 双平台实跑对照

两个平台都是**从 s1992.zip 解压到全新空目录**后跑同一套命令，不依赖预先存在的 src/ 或已在跑的服务。

## 1. 环境

| 项 | Windows | Ubuntu |
| --- | --- | --- |
| 主机 | DESKTOP-6BLPI5P | a-VMware |
| 系统 | Windows 11 (win32) | Ubuntu 24.04.5 LTS |
| Python | 3.11.7 | 3.12.3 |
| pytest | 9.1.1 | 7.4.4 |
| node | 无 | v18.19.1 |

本单是纯 Python 后端交付（评分器 + 归一化函数 + 夹具），不含前端，所以 node 是否可用不影响结论。

## 2. 结果对照

| 检查项 | Windows | Ubuntu |
| --- | --- | --- |
| `tools/gen.py` | rc=0，34 用例 / 手算表 306 行 | rc=0，同 |
| `tools/verify.py` | **SUMMARY 20/20 PASS** | **SUMMARY 20/20 PASS** |
| `pytest tests` | **68 passed** | **68 passed** |
| `tools/mutate.py` | **CAUGHT 11 / MISSED 0 / INVALID 0** | **CAUGHT 11 / MISSED 0 / INVALID 0** |
| `tools/pii_scan.py .` | scanned=56 hits=0 | scanned=55 hits=0 |
| 解压后首次 `sha256sum -c` | 0 mismatches | 0 mismatches |
| 跑完整套后 `sha256sum -c` | **55 files, 0 mismatches** | **55 files, 0 mismatches** |

`pii_scan` 的 scanned 差 1 是因为两侧可扫描文件数不同（Ubuntu 侧没有 `__pycache__` 里的残留），判据只看 `hits=0`。

## 3. 产物逐字节比对

| 文件 | sha256（两平台相同） |
| --- | --- |
| data/cases.jsonl | 28d16b1cf236dba8f61a662134623da2e4b8d0b8cf2f2b8abac196d6333e103c |
| data/field_schema.json | ae57a2d2b4908a487211e478e5e17bc5df57718ed4051ab2ad2c5a525c84d8e8 |
| data/handcalc.csv | 942d335e1fb89cc90185f101410d3844f3c3badaee315b183df67ebc6ae49279 |

## 4. 为什么 precision/recall/F1 可信

手算表 `data/handcalc.csv` 由 `fractions.Fraction` 整数运算**独立生成**，与评分器的浮点实现是两条路径。verify.py 逐用例逐字段比对到小数点后 12 位，并断言手算表自身自洽（分子分母与计数对得上）。这不是「自己算完和自己比」。

## 5. 复跑命令

```
unzip s1992.zip -d fresh && cd fresh
sha256sum -c SHA256SUMS.txt
python tools/gen.py
python tools/verify.py
python -m pytest tests -q
python tools/mutate.py
python tools/pii_scan.py .
```
