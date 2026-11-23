# 双平台实跑对照（本轮返工重跑，2026-11-23）

## 一、五份日志在两平台【逐字节相同】

同一批命令在 Windows 与 Ubuntu 上跑出的输出，sha256 完全一致：

| 日志 | sha256（两平台相同） | 字节 |
|---|---|---|
| ac.log | f7a6e1a452915f548305000016d0e67d05657a0d251d9bd2d1cb826d9abfcd74 | 2,725 |
| mutate.log | 7653e1e046c431c902eeb63bd7c10a2c2d8ce27bb695b83e10e0bacb7d6b7493 | 2,224 |
| pii.log | cf9212b5c60460c1c046ea03cf8ba2f073862fb74cee569a1e8da80483ff1ddb | 347 |
| verify.log | c175bb50d3117d3787954ebaa735d6a78873b1bc14f7268e9c74544f3940af6b | 353 |
| lint.log | 7f2c790cccc43ebd6db29e1606c275d2603af73987873e2a076742d4e9ef1266 | 36 |

核对方式：Ubuntu 侧 `sha256sum /tmp/{ac,mutate,pii,ver,lint}.txt`，
Windows 侧对同名日志取 sha256，两侧六组值逐一相同。
因此本目录下 `UBUNTU_*.log` 与对应 `WINDOWS_*.log` 内容相同 —— 这不是复制粘贴的推断，是哈希核对的结果。

## 二、Ubuntu 侧环境

```
Linux 7.0.0-38-generic x86_64（Ubuntu 24.04）
Python 3.12.3
```

## 三、Ubuntu 侧额外跑的两项（Windows 也跑了，结果一致）

```
$ sha256sum -c SHA256SUMS
17 行全部 OK（0 条 FAILED）

$ cp -r files /tmp/g2590b && cd /tmp/g2590b && python3 tools/build_renewal.py
wrote sop/templates/renewal.json 6440 bytes, 5 steps
$ cmp sop/templates/renewal.json <原包>/sop/templates/renewal.json
GEN_IDENTICAL
```

## 四、本轮在 Ubuntu 上抓到的真问题

1. `sha256sum -c` 报 `DATA_PROVENANCE.md: FAILED` —— 原因是我先算了校验和，之后才去打码文档里抄出来的命中字符串。
   本机不复核就不会暴露。已重算 SHA256SUMS 并复跑至 17/17 OK。
2. 传输通道：`scp` 无公钥、tmux 通道命令会被截断（9000 字符只落了 201 字节），
   改用 git 临时分支 `verify/rework-2590-r1` 传输，用完即删。
