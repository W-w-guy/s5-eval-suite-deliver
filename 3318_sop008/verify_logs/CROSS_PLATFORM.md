# CROSS_PLATFORM — 双平台实跑对照

两个平台都是**从 match3318.zip 解压到全新空目录**后跑同一套命令，不存在“本机已有 src/ 或服务在跑”的前提。

## 1. 环境

| 项 | Windows | Ubuntu |
| --- | --- | --- |
| 主机 | DESKTOP-6BLPI5P | a-VMware |
| 系统 | Windows 11 (win32) | Ubuntu 24.04.5 LTS |
| 内核 | — | 7.0.0-38-generic |
| Python | 3.11.7 | 3.12.3 |
| 路径分隔符 | `\` | `/` |
| 换行 | 文件一律 LF（`newline="\n"` 显式写入），子进程输出 CRLF 但入日志前统一 | LF |

## 2. 结果对照

| 检查项 | Windows | Ubuntu |
| --- | --- | --- |
| `tools/gen.py` | rc=0，examples=10 categories=8 | rc=0，examples=10 categories=8 |
| `tools/verify.py` | **SUMMARY 23/23 PASS** | **SUMMARY 23/23 PASS** |
| `pytest tests` | **11 passed** | **11 passed** |
| `tools/mutate.py` | **MUTATION PASS（7/7 被抓到）** | **MUTATION PASS（7/7 被抓到）** |
| `tools/pii_scan.py .` | scanned=34 hits=0 | scanned=32 hits=0 |
| 跑完整套后 `sha256sum -c` | **33 files, 0 mismatches** | **0 mismatches** |
| 解压后首次 `sha256sum -c` | 0 mismatches | 0 mismatches |

`pii_scan` 的 scanned 数不同是正常的：它扫的是“当前目录下可扫描的文件”，Ubuntu 侧解压目录里少了 `verify_logs/`（该目录不进包），且 `__pycache__` 内容不同。判据只看 `hits=0`。

## 3. 产物逐字节比对（关键证据）

7 份生成物在两平台**逐字节相同**（sha256 全等）：

| 文件 | sha256 |
| --- | --- |
| docs/match_sop.md | cfb80c0a3b501e919b25eb378426277957e3e14b3cdd2f56bb6906b65237bde2 |
| docs/match_steps.json | a78c1793fa1d19c87566ce695807b48bc64bba1bb9efcee75c94138817820a3b |
| docs/match_scripts.csv | 02c0830699c5a523ab8ce37f5fd42a2b86409c25e7cb3f7c05c16430f6ec9745 |
| docs/pre_brief_template.md | 22a057f91af9e07267033251dbc933778dd45bef36faa542721033def3dd6476 |
| docs/referral_flow.md | 2d1a6572d6f19f8c0b88c7403417f92345ea4712aa63333041e107aebc569c22 |
| docs/coverage.csv | f3f65e5f11e4dbaf7c445428fd704187263384e88f67f84c11de0ce6d24ec88c |
| docs/match_expected.csv | 4d535242d2832e06a8fba44ebe8cac32411fa5bd465b77d1330e90439018ce0a |

这说明产物内容完全由代码与固定输入决定，不含时间戳、随机数或平台相关的换行差异。

## 4. 唯一未纳入逐字节比对的文件

`docs/match_tables.xlsx` **不做**字节比对，也不进 `SHA256SUMS`。原因：xlsx 是 zip 容器，openpyxl 写入的条目带本地时间与 `create_system`，同机连跑两次字节都不同，跨平台更不可能相等。它的正确性由 `docs/match_expected.csv` 与 `verify.py` 的 V21/V22（引擎重算 10 行 × 12 列与 CSV 全等）保证。

## 5. 故意没做的事

- 未引入任何第三方依赖，`verify.py` / `pytest` 只依赖标准库 + pytest。
- 时间基准一律 naive datetime，不读系统时区，因此不依赖 tzdata（避开 Windows 上 `ZoneInfoNotFoundError` 的老坑）。

## 6. 复跑命令

```
unzip match3318.zip -d fresh && cd fresh
sha256sum -c SHA256SUMS.txt        # 应为 0 不一致
python tools/gen.py                # 重新生成 docs/
python tools/verify.py             # 23 条 AC 断言，任何失败即非零退出
python -m pytest tests -q          # 11 项
python tools/mutate.py             # 改坏 7 处，每处都必须让 verify 变红
python tools/pii_scan.py .         # 应为 hits=0
```
