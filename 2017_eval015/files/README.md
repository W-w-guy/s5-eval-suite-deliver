# S5-EVAL-015 个人 IP 内容助手评测集 ip_content.podcast

## 一句话
30 条用例（单集提纲 12 / 节目摘要 18）+ 18 份 3000–6000 字虚构转写稿（带时间戳）+
三项程序化检查脚本（金句逐字、时间戳单调、摘要数字有据）。

## 目录
```
data/cases.jsonl            30 条用例
data/transcripts/*.txt      18 份虚构访谈转写稿（3159–5577 字，带 [mm:ss] 时间戳）
ip_eval/checks.py           三项检查 + 提纲结构检查
ip_eval/__main__.py         runner（摘要/提纲生成 -> 检查 -> 报告）
tools/gen_cases.py          用例与转写稿同源生成器
suite_2017.yaml             套件定义
tests/                      28 个 pytest（正反夹具都覆盖）
verify_2017.py              4 条 AC 的 30 项断言
```

## 数据来源（复核要问的第一个问题）

全部数据为**虚构合成**，无任何外部来源：不使用公开数据集、不抓取网页、不使用客户数据。
每一份夹具都能由包内脚本重新生成，生成方式、种子、规模、哈希与 pii 扫描证据逐条写在
**`DATA_PROVENANCE.md`**，可直接用 `python tools/provenance.py check` 复核。


## 怎么跑
```bash
python -m ip_eval                                  # 全通过 rc=0
python -m ip_eval --break-quote --tag bq           # 金句改写 -> 逐字检查失败
python -m ip_eval --break-timestamp --tag bt       # 时间戳乱序 -> 单调检查失败
python -m ip_eval --break-number --tag bn          # 摘要编数字 -> 数字检查失败
python -m pytest tests -q                          # 28 项
python verify_2017.py                              # 30 项 AC 断言
```

## 实测

| 项 | 值 |
|---|---|
| 用例 | 30（提纲 12 / 摘要 18） |
| 转写字数 | 3159 – 5577（全部落在 3000–6000，且覆盖整个区间） |
| 通过率 | **1.0000**（提纲 1.0 / 摘要 1.0） |

三个破坏方向各自触发对应检查（不是同一个原因兜底）：

| 开关 | 触发的检查 | 报错原文 |
|---|---|---|
| `--break-quote` | 金句逐字 | 「有 1 条金句在转写稿中查不到原文」 |
| `--break-timestamp` | 时间戳单调 | 「时间戳非单调递增」 |
| `--break-number` | 摘要数字 | 「有 1 个数字不在转写稿中：['999999']」 |

## 五件必须先说清的事

**1. 三项检查都必须「正反夹具都测」。**
只测「合规输出能通过」毫无意义——「永远返回通过」的实现也能过。
所以 `tests/test_checks.py` 里每一项都有反例：金句改一个字、时间戳乱序、时间戳超总时长、
摘要编一个不存在的数字、提纲漏追问、提纲碰不谈话题。

**2. 转写字数不能只凑到区间端点。**
初版 `pad_to_range` 只补到 >=3000 就停，18 份全落在 3001–3035 —— 名义上「都在区间内」，
但完全没覆盖 3000–6000 的分布，等于测不出长稿上的摘要压缩率。已改为按 idx 均分到 3200–5600。

**3. 时间戳检查要接受多种输入形态。**
初版只处理 `"03:20"` 字符串与秒数；而 runner 传的是 `{"ts": "03:20", "title": ...}` 章节对象，
`str()` 出来是 `"{'ts': ...}"`，解析必失败 —— 18 条摘要用例全被判「存在无法解析的时间戳」，
通过率一度是 0。已支持三种形态（秒数 / 字符串 / dict）。

**4. 金句必须是原句，不能改写。**
检查口径是「归一化空白后逐字包含」。多一个空格算通过，改一个字算失败 ——
这条边界在测试里两个方向都断言了。

**5. 提纲的不谈话题是硬约束。**
嘉宾资料里声明的「不谈话题」（如正在进行的融资细节、上一家公司离职原因），
若出现在开场白或任一板块标题/追问里，直接判失败。


## 验收对照表（AC1–AC4 逐条可核）

| AC | 验收要求 | 实测结果 | 复核命令 |
|---|---|---|---|
| AC1 | cases.jsonl 恰有 30 条（提纲 12、摘要 18），eval-lint 与 eval-pii-scan 均通过 | **30 条**，outline 12 / summary 18；`LINT PASS errors=0`；`PII PASS hits=0`（21 个文本文件全扫） | `python tools/lint.py` 与 `python tools/eval_pii_scan.py` |
| AC2 | 金句逐字检查与时间戳单调检查对正反夹具判断正确（单元测试） | 正夹具通过、反夹具（改一个字）失败；时间戳正夹具通过、乱序失败、超总时长失败 | `python -m pytest tests -q` → 28 passed |
| AC3 | 18 份转写稿字数均在 3000–6000 | 实测区间 **3159–5577**，max−min = 2418 | `python verify_2017.py` |
| AC4 | 用 echo mock 跑通 eval-run 并生成报告 | rc=0，`reports/ip_v1.md`：通过率 1.0000（提纲 1.0000 / 摘要 1.0000） | `python tools/eval_run.py` |

一条命令全验：`python verify_2017.py` → `TOTAL 30, PASS 30, FAIL 0`（另有 `--self-test` 反向自测通过）。

## AC1 的两项检查具体输出

本包把 lint 与 pii 做成了两个独立命令行工具（也可由 `verify_2017.py` 内联复核）：

```
$ python tools/eval_lint.py
cases=30 dist={'summary': 18, 'outline': 12} errors=0
LINT PASS

$ python tools/eval_pii_scan.py
scanned_files=19
hits=0
PII PASS
```

- `eval-lint`：30 条、分布 12/18、case_id 唯一、每条有 forbidden_points；
  提纲档必含 guest/background/topic/off_limit_topic，摘要档必含存在的转写稿文件、3 条金标金句、字数 3000–6000。
- `eval-pii-scan`：19 个文件（18 份转写稿 + 1 份 cases.jsonl）逐份扫手机号/邮箱/身份证形态，**0 命中**。
- 两个工具都有反向用例证明不是恒真（见 `tests/test_checks.py`）：
  lint 对结构缺失的用例必报 FAIL；pii 在文本里植入真邮箱时必报 FAIL。

## 已知局限（如实写）
- 被测工具是 echo mock（正则抽取 + 模板生成），不是真实 LLM；它证明的是检查链路与判定口径有效。
- 摘要长度上限 300 字在 mock 里靠字符截断实现，真实模型会做语义压缩，压缩率不可比。
- 30 条只够验证链路与门槛，不够估置信区间。
- 「摘要是否添加了嘉宾没说过的话」只做了数字级检查（数字必须在稿里），
  语义级编造需接 EVAL-004 的评审模型逐句判断。
