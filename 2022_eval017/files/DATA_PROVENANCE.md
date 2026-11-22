# 数据来源与可复核性（DATA_PROVENANCE）—— #2022 S5-EVAL-017

本包所有数据均为**程序化虚构生成**，无任何外部数据源、无网络请求、不含真实个人或企业信息。

## 一、生成脚本与种子

| 项 | 值 |
|---|---|
| 生成脚本 | `tools/gen_cases.py` |
| sha256 | `f576ecb18fdfb1a84a05fc32a92263ef6aebf992524c9d62da10c551d3cc8d8a` |
| 固定种子 | `random.Random(2022)` |
| 重跑命令 | `python tools/gen_cases.py` |
| 产出规模 | 35 条用例 + 35 份 context（每份 8~20 篇资讯，合计 12 个事件素材池循环复用） |
| 产物 sha256 | `data/cases.jsonl` = `ac5a5090b96fc0e6c7fc39f4d7418300c2edc47a780c6a225ba8c1db428ae63d` |

重跑后 `data/cases.jsonl` 与 `contexts/*.json` 与本包内置文件**逐字节一致**（确定性常量表 + 固定种子，
无 `time.time()` / `os.urandom` / `uuid4`）。已实测：删掉 `data/` 与 `contexts/` 后重跑，sha256 不变；
Windows（Py3.11.7）与 Ubuntu（Py3.12.3）两侧重跑结果亦相同。

> ★ 一个必须显式处理的坑：Python 在 Windows 用文本模式写文件默认换行是 CRLF，Linux 是 LF。
> 同一份 `cases.jsonl` 两侧 sha256 会不同（每行差 1 字节）。所以本脚本所有 `open(..., "w")`
> 都显式写了 `newline="\n"`，跨平台字节一致才成立。此前正是漏了这一点，导致 Ubuntu 上重跑后
> `sha256sum -c` 报 5 个文件 FAILED。

## 二、虚构内容来源（逐类）

| 数据 | 来源 | 可复核方式 |
|---|---|---|
| 20 个事件素材（主体/动作/关键数字/类别） | `tools/gen_cases.py` 常量表 `EVENTS` | 打开文件第 28~50 行 |
| 4 套表述模板（措辞不同） | 常量表 `TEMPLATES` | 同上 |
| 地域/来源/行业池 | `AREAS` / `SOURCES` / `INDUSTRIES` | 同上 |
| 35 条用例的 gold 聚类/分类/Top5 | `build_case()` 由素材池 + 种子确定性推导 | `python tools/lint.py --lint` 校验 gold 与 context 一致 |
| 会员行业画像 | `build_case()` 内按用例序派生（行业 + 地域 + 兴趣类别） | 同上 |

企业名统一使用「示例××」前缀（示例云栈科技、示例海纳物流…），地名使用「示例市/近江新区」等虚构名，
不含任何真实企业或地名。

## 三、PII 扫描证据

```
python tools/lint.py --pii
```

- 扫描范围：包内 `.py/.md/.json/.jsonl/.yaml/.txt` 实测 49 个文件（干净解压后；跑过 pytest 会多出 `.pytest_cache`，故扫描数会变，断言只认 `unexpected=0`）。
- 规则：手机号 `1[3-9]\d{9}`（只接受 `1990000` 虚构段）、邮箱（只接受 `.invalid` 保留域）、身份证 `\d{17}[\dXx]`。
- 结论：`unexpected=0` —— 包内不存在任何真实格式的手机号/邮箱/身份证。
- 身份证正则额外限定「前后不得是十六进制字符」：sha256 清单里 64 位十六进制常含 18 位连续数字，
  旧写法会把它误判成身份证（实测撞到过 1 例）。

## 四、不出现客户名称

全包只使用「会员空间平台」这一通用称谓；工单原文中的客户信息未落入任何交付文件。

## 五、零第三方运行时依赖

`verify_2022.py` / `tools/*.py` 只用 Python 3.11+ 标准库；`pytest` 仅用于 `tests/` 单元测试环节。

## 六、报告是生成物，不参与校验和

`reports/triage_v1.md` / `triage_v1.json` 是 `tools/eval_run.py` 每次运行的产物，
内容含运行时路径，**故意不列入 `SHA256SUMS.txt`**——否则买家跑一次 eval-run 就会报校验失败。
校验和只覆盖源码、数据、context 与说明文档。
