# DATA_PROVENANCE.md · 数据来源与可复核性

> 工单要求「示例数据虚构」。本文不是「全部虚构」一句话，而是给出**生成脚本 + sha256 + 种子 + 重跑命令 + 产出规模 + pii 扫描结果**，让买家可以自己复核。

## 一、数据从哪来

本包**没有外部数据源**。`sop/templates/renewal.json` 由生成器从一份内嵌常量字典生成
（`docs/*.md` 依据这份模板整理，并有测试断言二者不漂移，见第三节末尾）：

| 项 | 值 |
|---|---|
| 生成脚本 | `tools/build_renewal.py` |
| sha256 | `cf264bf505323cffe45580f6faf25903d06967e3920a924a811c32137b160e62` |
| 大小 | 6,871 字节 |
| 随机性 | **无随机数**。模板是常量字典，`random` 未被 import |
| 外部依赖 | 仅标准库 `json` / `os` / `datetime` |
| 重跑命令 | `python tools/build_renewal.py` |
| 重跑产出 | `sop/templates/renewal.json`（6,440 字节，5 步） |
| 重跑幂等性 | 已在全新临时目录实跑验证：产出 sha256 = `8420dcb9e8f1c3807042e12e717e182aec9f2cbfb2a61fbe76cf366d1b9d6bf1`，与包内文件**逐字节相同** |

## 二、产出规模（可直接数）

| 交付物 | 规模 | 可数方式 |
|---|---|---|
| `sop/templates/renewal.json` | 5 个步骤、4 本字典、4 条话术 | `python -c "import json;t=json.load(open('sop/templates/renewal.json'));print(len(t['steps']),{k:len(v) for k,v in t['dictionaries'].items()})"` |
| 字典词条 | risk_reason 8 / renewal_intent 5 / care_action 6 / outcome 3 | 同上 |
| `docs/steps-renewal.md` | 75 行，逐步说明 | `wc -l docs/steps-renewal.md` |
| `docs/scripts-renewal.md` | 4 段话术 | `wc -l` |

## 三、虚构性怎么保证（三层，不是一句声明）

### 第 1 层：内容里禁用真实信息形态

`sop/schema.json` 的 `forbidden_pii` 列了三条正则（手机号 / 邮箱 / 身份证），`sop/lint.py` 的 `_content()` 对模板**所有字符串值**逐个扫描，命中即报 **E030 ERROR**。

放行条件写死在 `_is_virtual()`：手机号尾 4 位为 `0000`/`8888`，或邮箱域名属于 RFC 2606 保留域。**这不是「看着像假的就放行」，是白名单式判定。**

变异测试里专门有两条，把假号码与假邮箱注入话术，断言 lint 必须报 E030：

```
检出  renewal: 话术里写入真实手机号 -> E030
检出  renewal: 话术里写入真实邮箱 -> E030
```

### 第 2 层：整包 pii 扫描

`tools/pii_scan.py` 扫描包内全部 `.py/.md/.json/.txt` 文件，四类形态（手机 / 邮箱 / 18 位身份证 / 统一社会信用代码）：

```
$ python tools/pii_scan.py
pii_scan files=16 raw_hits=2 allowed=2 unexpected=0
  ALLOWED tests/mutate.py:80 phone 1381****678 （变异测试注入的坏值，非交付内容）
  ALLOWED tests/mutate.py:82 email li**@**.com （变异测试注入的坏值，非交付内容）
PII PASS（unexpected=0；手机/邮箱/身份证/信用代码 四类形态均无真实信息）
```

**本文件里这两行输出已打码**：原样抄出被扫描器命中的字符串，会让本文件自己变成新的命中源（第一版就这样把自己扫红了）。
打码后仍保留行号与类别，可复核。

**这里如实说明那 2 条 `ALLOWED` 是什么**：变异测试必须注入「形如真实」的号码与邮箱，才能证明 lint 的 E030 真的会报错。这两条字符串**只作为被注入的坏值**存在于 `tests/mutate.py`，不在任何交付内容（模板、文档、话术）里。扫描器逐行判定豁免，并把豁免条数单独打印（`allowed=2`），不会被静默吞掉。交付内容本体（`sop/templates/` `docs/`）扫描结果 0 命中。

### 第 3 层：不含客户名称

包内对「会员空间」「商务会员」「会员空间平台」等客户侧标识做了全文扫描，**0 命中**。复核命令：

```bash
grep -rn "会员空间\|商务会员" . --include=*.py --include=*.md --include=*.json   # 期望无输出
```

## 四、这个包的「虚构数据」到底指什么

本单是**模板配置**，不是数据集。所谓示例数据 = 模板里的字典词条与话术占位符（`{联系人}` / `{企业名称}` 等 11 个变量，定义在 `sop/schema.json:allowed_vars`）。运行测试时用的虚构会员（`m1`、健康分 60/39、`expire_at=2026-05-31`）全部写在 `tests/test_renewal_ac.py` 的构造函数里，**不落盘、不进交付内容**。

## 五、可复核的一句话

```bash
python tools/build_renewal.py          # 重跑生成，与包内文件逐字节相同
python tools/pii_scan.py               # unexpected=0
python verify.py                       # lint / AC / 变异 全绿
```

## 六、文档与模板不漂移（本轮返工新增）

`docs/steps-renewal.md` 与 `docs/scripts-renewal.md` 是**依据模板整理**的说明文档，不是独立事实源。
为防止文档写着模板里没有的东西，测试里加了文档一致性断言（`test_docs_match_template`）：

- 模板里每个步骤的 `id` / `name` / `role` / `required_outputs` 必须都能在 `docs/steps-renewal.md` 找到对应行；
- 话术文档里的段落数必须等于模板 `scripts` 的键数。

改模板而忘了改文档时，这三类断言会红。复核：

```bash
python tests/test_renewal_ac.py     # 期望含 PASS  DOC1 / DOC2 / DOC3
```
