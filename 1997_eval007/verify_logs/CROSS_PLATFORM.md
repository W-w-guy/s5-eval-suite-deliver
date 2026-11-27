# CROSS_PLATFORM — 双平台实跑对照

两个平台都是**从 s1997.zip 解压到全新空目录**后跑同一套命令。

## 1. 环境

| 项 | Windows | Ubuntu |
| --- | --- | --- |
| 主机 | DESKTOP-6BLPI5P | a-VMware |
| 系统 | Windows 11 (win32) | Ubuntu 24.04.5 LTS |
| Python | 3.11.7 | 3.12.3 |
| 内核 | — | 7.0.0-38-generic |

纯 Python 交付（标准库 + pytest），无第三方运行时依赖，无 node 依赖。

## 2. 结果对照

| 检查项 | Windows | Ubuntu |
| --- | --- | --- |
| 解压后 `sha256sum -c SHA256SUMS.txt` | 0 mismatches | 0 mismatches |
| `tools/verify.py` | **SUMMARY 31/31 PASS** | **SUMMARY 31/31 PASS** |
| `pytest tests` | **60 passed** | **60 passed** |
| `tools/mutate.py` | **CAUGHT 14 / MISSED 0 / INVALID 0** | **CAUGHT 14 / MISSED 0 / INVALID 0** |
| 跑完整套后 `sha256sum -c` | **52 files, 0 mismatches** | **0 mismatches** |

## 3. 性能（AC4）双平台实测

性能夹具 1000 条 JSONL 用例，其中每 97 条插 1 条含手机号+身份证的命中样例（共 20 条 error 命中），测的是最坏情况而非快速跳过路径。预算 10000ms。

| 指标 | Windows | Ubuntu |
| --- | --- | --- |
| scanned | 1000 | 1000 |
| cold_ms（冷启动） | 73.0 | 59.1 |
| warm_best_ms（预热 2 轮后取 3 次最小值） | **61.4** | **52.1** |
| per_case_ms（单条平均） | 0.0614 | 0.0521 |
| 占预算比例 | 0.61% | 0.52% |

两平台稳态耗时都只有预算的 0.6% 左右，低两个数量级。

`docs/perf.json` 是**运行产物**，每次运行数值略有不同，因此**不进 SHA256SUMS**；上面的数值是两平台各自最后一次 build_docs 的实测结果，可在各自日志里逐字核对。

## 4. 生成物确定性（比日志相同更强的证据）

`README.md` 与 `ACCEPTANCE.md` 由 `tools/build_docs.py` 从实跑结果生成。两个平台**各自独立重新生成**后，sha256 完全相同：

| 文件 | Windows | Ubuntu |
| --- | --- | --- |
| README.md | b1c728793c32d83f310e493b279d981cda244c2fd9b34a812513a36d5eee1101 | 同 |
| ACCEPTANCE.md | e993b2658d5899fdafc559cf62b85575c49131e4810b5418e832f2af258dadec | 同 |

说明这两份文档的内容完全由代码与固定夹具决定，不含运行时刻、随机数或平台相关的换行差异。

## 5. 为什么 docs/perf.json 不进校验和

它每次运行都会变（上面 Windows 73.0 / 上一轮 76.6，同一台机器两次就不一样）。若把它列进 SHA256SUMS，买家跑一遍测试再校验就会报 mismatch，看起来像文件被篡改。所以 `make_zip.py` 的 `SKIP_SUMS_PREFIX` 显式排除 `docs/perf.json` 与 `verify_logs/`，而「跑完整套后 0 mismatches」这条断言就是这个设计的验证。

## 6. 复跑命令

```
unzip s1997.zip -d fresh && cd fresh
sha256sum -c SHA256SUMS.txt
python tools/verify.py
python -m pytest tests -q
python tools/mutate.py
python tools/build_docs.py
```
