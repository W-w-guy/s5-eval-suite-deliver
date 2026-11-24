# 跨平台一致性记录 · 2023

两侧各自实跑，日志在 `verify_logs/`。本文件只记录**两侧可比对的结论**，不含推断。

## 一、结论表

| 检查项 | Windows 11 / Py3.11.7 | Ubuntu 24.04 / Py3.12.3 | 一致？ |
|---|---|---|---|
| `verify_2023.py` | TOTAL 26, PASS 26, FAIL 0 · rc=0 | TOTAL 26, PASS 26, FAIL 0 · rc=0 | ✅ |
| `pytest tests -q` | 20 passed | 20 passed | ✅ |
| `eval-lint` | errors=0 warnings=0 | errors=0 warnings=0 | ✅ |
| `eval-pii-scan` | files=83 unexpected_hits=0 | files=83 unexpected_hits=0 | ✅ |
| `python -m doc_eval` | field_acc=0.9900 flag_recall=0.9750 | field_acc=0.9900 flag_recall=0.9750 | ✅ |
| `gen` 同机连跑两次 | 83 文件逐字节相同 | 83 文件逐字节相同 | ✅ |
| `data/cases.jsonl` sha256 | `d7f950767758b3ccf8c9d61e16822fcc…` | 同左 | ✅ |
| `data/plain/**` 合并 sha256 | `3f1d7c2ecd2be2d4fe9e37a0c7317f12` | 同左 | ✅ |
| PDF 文件 sha256 | 与 Ubuntu 不同 | 与 Windows 不同 | ⚠ 已查明原因，见第二节 |

## 二、PDF 字节为何跨平台不同（已定位，非缺陷）

`tools/render_carriers.py` 生成 `text_pdf` 时把字体**子集化后内嵌**。字体按下列顺序查找，
第一个存在的即用：

```
Windows: C:\Windows\Fonts\simhei.ttf  (simhei)
Ubuntu : /usr/share/fonts/truetype/arphic/uming.ttc (AR PL UMing)
```

两份字体的字形轮廓与 hmtx 宽度不同 → 子集化出的字体字节不同 → PDF 字节不同。

**这不是随机性**：同一台机器上连跑两次 `gen_contracts.py`，83 个文件逐字节相同
（两侧都验证过，见第一节最后两行）。

**交付包内是 Windows 侧生成的那份固定产物**，买家解压即用，不需要重新生成数据。
`cases.jsonl` 与 `data/plain/` 与平台无关，两侧哈希完全相同，可直接核对。

## 三、为让字节可复现做的三处修复（都已验证）

| 问题 | 现象 | 修法 |
|---|---|---|
| `TTFont.save()` 默认 `recalcTimestamp=True` | 每次子集化字节都不同 | 置 `font.recalcTimestamp = False`，并显式把 `head.modified/created` 归零 |
| Pillow 写 PDF 时写入当前时间 | `/CreationDate`、`/ModDate` 每次不同 | 正则替换为等长固定值 `D:20260101000000Z`（**长度必须相等**，否则 xref 偏移错位，pypdf 报 `incorrect startxref pointer`） |
| `zipfile.writestr` 用当前时间 | docx 字节不可复现 | 固定 `ZipInfo.date_time=(2026,1,1,0,0,0)` 与 `create_system=0` |

前两处最初未修时，Ubuntu 侧 `gen` 连跑两次出现 27 个 PDF 字节不同；修复后为 0。

## 四、怎么自己复核这张表

```bash
# Windows 或 Ubuntu 任一侧
python tools/gen_contracts.py && sha256sum data/cases.jsonl
python -c "import hashlib,os;h=hashlib.sha256();[h.update(open(os.path.join(r,x),'rb').read()) for r,d,f in sorted(os.walk('data/plain')) for x in sorted(f)];print(h.hexdigest()[:32])"
```
两侧输出应与第一节最后两行一致。
