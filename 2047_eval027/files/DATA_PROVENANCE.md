# 数据来源与可复核性（DATA_PROVENANCE）—— #2047 S5-EVAL-027

本包所有数据均为**程序化虚构生成**，无任何外部数据源、无网络请求、不含真实个人或企业信息。

## 一、生成脚本与种子

| 项 | 值 |
|---|---|
| 生成脚本 | `tools/gen_all.py` |
| sha256 | `d0519668b30b2004d71c0d6de66102da700c57621fec6f5bde104e936f580c40` |
| 固定种子 | `random.Random(2047)`（脚本第 12 行） |
| 重跑命令 | `python tools/gen_all.py` |
| 产出规模 | 45 条用例 + 6 条金丝雀联系人 + 10 篇受限文档 + 7 个虚构身份 + 4 个夹具文件 |
| 产物 sha256 | `data/guardrail_leakage_cases.jsonl` = `ce6657071a5ce5b594ee8d7ac13f61ee23621dabd4aa246e6e30c59f465d6094` |

重跑后 `data/guardrail_leakage_cases.jsonl` 与本包内置文件**逐字节一致**（固定种子 + 确定性常量表，
无 `time.time()`、无 `os.urandom`、无 `uuid4`）。此项已实测：删掉 `data/` 与 `fixtures/` 后重跑，sha256 不变。

## 二、四类虚构数据的来源说明

| 数据 | 来源 | 可复核方式 |
|---|---|---|
| 7 个身份（`fixtures/identities.json`） | 脚本内常量表 `IDENTITIES`（企业名「示例会员企业甲/乙」等） | 打开 `tools/gen_all.py` 第 20~34 行 |
| 10 篇受限文档（`fixtures/docs.json`） | 脚本内常量表 `DOCS` + 模板拼接 | 同上，`DOC_TAGS`/`DOC_SCOPES` |
| 6 条金丝雀联系人 | `core.canary_phone/canary_email` 由 md5(seed) 派生 | `python tools/pii_scan.py` 打印全清单 |
| 45 条用例正文 | 6 类手法模板 × 三入口 × 目标组合 | `python tools/lint.py 2047` 打印分布 |

## 三、PII 扫描证据

```
python tools/pii_scan.py
```

```
canary fixtures=6 all_impossible=True
  C-01 19900002876 canary-12f6fcaa@guardrail.invalid
  ...（共 6 条）
unexpected=0
PII PASS
```

- 扫描规则：手机号 `1[3-9]\d{9}`、邮箱 `...@...`、身份证 `\d{17}[\dXx]` 三类形态。
- 结论：命中全部为登记在册的金丝雀（`unexpected=0`），**包内不存在任何非金丝雀的 PII 形态**；身份证形态 0 命中。
- 邮箱使用 `.invalid`（RFC 2606 保留域，永不解析）→ 规范级不可能存在。
- 号码使用 `1990000\d{4}` → 结构约束 + 清单登记；此项为**近似口径**，不据此声称「运营商必不分配」。
- 扫描覆盖包内全部 `.py/.md/.json/.jsonl/.yaml/.txt` 文件（排除 `.pyc`/二进制）。

## 四、不出现客户名称

全包检索 `会员空间平台` 之外无客户名；工单原文中的客户信息未落入任何交付文件。
交付物仅描述「会员空间平台」这一通用称谓。

## 五、零第三方运行时依赖

除 Python 3.11+ 标准库外，运行 `verify.py` / `tools/*.py` / `pytest` 不需要任何第三方包
（`pytest` 仅用于单元测试环节，缺失时 `verify.py` 内的 pytest 子项会失败而其余项仍可跑）。
