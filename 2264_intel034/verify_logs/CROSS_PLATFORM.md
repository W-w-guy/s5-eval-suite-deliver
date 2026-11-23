# 双平台实跑对照 · 2264（返工 ver2）

## 一、哪些日志在两平台逐字节相同

同一批命令在 Windows 10 / Python 3.11.7 与 Ubuntu 24.04 / Python 3.12.3 上跑，
下列日志 sha256 **完全相同**（不是「看起来一样」，是哈希相同）：

| 日志 | sha256 | 字节 |
|---|---|---|
| verify.log（34 项 AC 断言） | b4beda6d0e22684896750496562a9754add63557eeaa63973b37cc2f5d5949bb | 2,089 |
| pytest.log | 15503b10fdec850e5e25683ea219523abd3be733479ab430cd75077823dbe6f2 | 160 |
| pii.log | ec57fc2ec2f16af6d83bcbf9e73a031b1ae4a4f645528b574f424bf2c25a6f19 | 845 |

## 二、哪些日志只差绝对路径（其余逐字节相同）

三次 `run` 的输出里有一行 `report=<绝对路径>`，两平台的仓库位置不同，所以整文件哈希不同。
把这一行替换成对方的路径后重新算哈希，**与对方的实际哈希完全相等**：

| 日志 | 替换后哈希 | 对方实际哈希 | 结论 |
|---|---|---|---|
| run_v1.log | de0d11bd1b811bad86b95f8fd07b27e257e1dfffe5ceba04504d46f8d89ab07a | 同左 | 只差路径 |
| run_v2.log | 949e73eac9d97edbfca2edf5bce243c28eed439eec36741b88788b2226a14301 | 同左 | 只差路径 |
| run_ci_bad.log | 73d06b1b24e7fec2bb6f6907cf830572579a87a8adca3cd02978c7eca4faf0e5 | 同左 | 只差路径 |

## 三、Ubuntu 侧另外验证的四件事

```
1) sha256sum -c SHA256SUMS  ->  40/40 OK，0 条 FAILED
2) 删掉 reports/ 后重跑 v1 / v2 / ci_bad / compare
   -> 重新生成的 7 份交付报告与仓库内版本【逐字节相同】（SAME × 7）
   这是跨平台确定性证据：报告产物在 Windows 生成、Ubuntu 复现，字节一致。
3) python3 tools/gen_site.py 重跑生成器
   -> data/gold.jsonl、robots.txt、a001.html 与包内 cmp 相同（SAME × 3）
4) python3 -m pytest tests -q  ->  79 passed
   python3 verify_2264.py      ->  TOTAL 34, PASS 34, FAIL 0
```

## 四、这一轮在 Ubuntu 上暴露的问题（都已修）

1. **Windows 侧日志是 CRLF**：子进程 stdout 在 Windows 文本模式下把 `\n` 写成 `\r\n`，
   导致同一份输出在两平台字节数相差恰好等于行数（verify.log 2,125 vs 2,089 = 36 行）。
   已统一为 LF 后再比对，才得到上表的「完全相同」。
   → 教训：跨平台比哈希之前必须先统一换行，否则会把「格式差异」误报成「内容差异」。
2. **pii 的 `files=` 计数会漂**：Ubuntu 上跑过 pytest 后 `reports/` 多了 11 个产物文件，
   计数从 46 变成 57。判据只能是 `unexpected=0`，不能把 `files=46` 当契约。
   交付包里 `reports/` 已固定为 7 份交付产物，开包即验时就是 46。

## 五、复现命令

```bash
cd files
sha256sum -c SHA256SUMS
python3 -m pytest tests -q
python3 verify_2264.py
python3 -m intel_eval run --prompt-set v2     # rc=0
python3 -m intel_eval run --prompt-set v1     # rc=1（低分对照）
python3 -m intel_eval run --prompt-set ci_bad --ignore-robots   # rc=1（robots 反例）
python3 -m intel_eval compare --a v1 --b v2
```
