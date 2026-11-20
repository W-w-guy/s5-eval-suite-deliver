# S5 评测套件交付 · 5 单
会员空间平台 Stage v「评测、红队与质量月报」模块的 5 个评测套件交付件。
**所有数据均为虚构**：企业、资源、嘉宾、访谈转写稿、知识库政策与常见问题全部原创编写，不含任何真实个人或企业信息。每个包内都有 `eval-pii-scan`（手机号/邮箱/身份证形态）自检，全部 0 命中。
## 一、索引

| 目录 | 工单 | 交付件 | 条目 | 大小 | sha256(前16) |
|---|---|---|---|---|---|
| `1989_eval004/` | S5-EVAL-004 | `eval1989_deliver.zip` | 21 | 35,226 B | `0cb3975393af4d7c` |
| `2008_eval012/` | S5-EVAL-012 | `match2008_deliver.zip` | 52 | 45,490 B | `0273d28a2bd3a25c` |
| `2017_eval015/` | S5-EVAL-015 | `ip2017_deliver.zip` | 35 | 61,911 B | `00682bd2240f564b` |
| `2033_eval022/` | S5-EVAL-022 | `kqa2033_deliver.zip` | 145 | 163,601 B | `505f62a30cf7c19d` |
| `2037_eval023/` | S5-EVAL-023 | `mt2037_deliver.zip` | 143 | 126,398 B | `6db494320cd5530e` |

## 二、逐单验收对照

### S5-EVAL-004 · 要点命中评分器：关键词规则与评审模型双轨打分

目录 `1989_eval004/`

**验收标准（原文）**

- 1. 一致性自检报告显示评审模型与人工一致率 ≥ 90%（附逐条对照表）
- 2. evidence_quote 不在输出原文中时该要点记为 no（mock 测试通过）
- 3. 命中 forbidden_points 的用例得分再高也判为不通过（测试断言）
- 4. 3 次评审结果不一致时用例带 judge_unstable 标记

### S5-EVAL-012 · 招商 AI 评测集：资源方匹配排序与推荐理由

目录 `2008_eval012/`

**验收标准（原文）**

- 1. cases.jsonl 恰有 35 条，eval-lint 与 eval-pii-scan 均通过
- 2. 9 条陷阱用例中被排除的资源都写在 forbidden_points 中（脚本检查）
- 3. recall@3 与 MRR 脚本对 5 组手算样例结果一致（单元测试通过）
- 4. 用 echo mock 跑通 eval-run 并在报告中显示 recall@3

### S5-EVAL-015 · 个人 IP 内容助手评测集：创始人播客提纲、摘要与金句

目录 `2017_eval015/`

**验收标准（原文）**

- 1. cases.jsonl 恰有 30 条（提纲 12、摘要 18），eval-lint 与 eval-pii-scan 均通过
- 2. 金句逐字检查与时间戳单调检查对正反夹具判断正确（单元测试通过）
- 3. 18 份转写稿字数均在 3000–6000 字之间（统计输出）
- 4. 用 echo mock 跑通 eval-run 并生成报告

### S5-EVAL-022 · 知识问答评测集：检索召回、答案要点与引用准确率

目录 `2033_eval022/`

**验收标准（原文）**

- 1. 知识文档恰有 120 篇，导入脚本在空知识库实例上执行成功（命令输出）
- 2. cases.jsonl 恰有 50 条，4 类分布与说明一致，eval-lint 与 eval-pii-scan 均通过
- 3. 每条用例的 gold_doc_ids 都能在知识文档中找到（脚本检查）
- 4. 用 echo mock 跑通 eval-run，报告中显示 recall@5 与引用准确率

### S5-EVAL-023 · 知识问答评测集：多轮追问、指代与条件变更

目录 `2037_eval023/`

**验收标准（原文）**

- 1. cases.jsonl 恰有 30 组对话，每组 3–5 轮，4 类分布与说明一致
- 2. eval-lint 与 eval-pii-scan 均通过（命令输出）
- 3. 8 组纠正类对话都把被纠正前提写入 forbidden_points（脚本检查）
- 4. 用 echo mock 按轮次跑通 eval-run，结果中可见每轮的检查点

## 三、怎么验收（每个包三条命令，零第三方依赖）

每个包**只依赖 Python 标准库**（`pytest` 仅用于跑测试，AST 逐文件解析 import 已确认无其他第三方包）。
解压后在该目录执行：

```bash
python verify_XXXX.py            # 按 AC 逐条断言的验收脚本，全 OK 才 rc=0
python verify_XXXX.py --self-test # 反向自测：把断言改坏必须变红（证断言不是摆设）
python -m pytest tests -q        # 单元测试
```

| 包 | 验收脚本 | AC 断言数 | pytest |
|---|---|---|---|
| `1989_eval004` | `verify_1989.py` | 32 | 53 |
| `2008_eval012` | `verify_2008.py` | 24 | 26 |
| `2017_eval015` | `verify_2017.py` | 30 | 28 |
| `2033_eval022` | `verify_2033.py` | 29 | 20 |
| `2037_eval023` | `verify_2037.py` | 25 | 22 |

（`--self-test` 对每个包都通过：断言可被打坏，说明校验不是恒真。）

## 四、双平台实测

交付前在 **Windows 11** 与 **Ubuntu 24.04.5 LTS / kernel 7.0.0-38 / Python 3.12.3** 各跑一遍，
Ubuntu 侧是把 zip 重新上传后解压到**新建临时目录**再跑，不与 Windows 共用目录。

| 包 | Windows pytest | Ubuntu pytest | Ubuntu verify | self-test |
|---|---|---|---|---|
| 1989 | 53 passed | 53 passed | 32/32 rc=0 | PASS |
| 2008 | 26 passed | 26 passed | 24/24 rc=0 | PASS |
| 2017 | 28 passed | 28 passed | 30/30 rc=0 | PASS |
| 2033 | 20 passed | 20 passed | 29/29 rc=0 | PASS |
| 2037 | 22 passed | 22 passed | 25/25 rc=0 | PASS |

Ubuntu 实跑原始日志在各自的 `verify_logs/UBUNTU_VM_20261120.log`。

## 五、必须如实说明的三点

**1. 被测系统是 echo mock，不是真实大模型。**
这是工单明确允许的（AC 里写的就是「用 echo mock 跑通 eval-run」）。它证明的是**评测链路、指标口径与判定逻辑有效**，
不代表真实模型的业务能力。每包 README 的「已知局限」一节都写了这一条，没有包装成已验证模型效果。

**2. 指标可被证伪。**
每包都带破坏开关，能把达标指标打成不达标，证明指标不是恒真：

| 包 | 破坏开关 | 效果 |
|---|---|---|
| 1989 | `assert_eligible` 低一致率 | 评分器拒绝启用，抛 `ScorerNotEligible` |
| 2008 | `--break-optout` / `--break-reason` | 推荐被排除资源 6 次 / 理由有据率下降 |
| 2017 | `--break-quote` / `--break-timestamp` / `--break-number` | 三类检查各自 rc=1 并有失败用例 |
| 2033 | `--break-citation` | 引用准确率 1.0000 → 0.4589，forbidden 触发 |
| 2037 | `--break-history` / `--break-stale` | 末轮命中 1.0 → 0.2667 / forbidden 0 → 8 次 |

**3. 规模只够验证链路，不够估置信区间。**
30/35/50 条的规模能验证门槛与判定口径，不能用于推断线上真实准确率。

## 六、环境

- Python 3.11+（实测 3.12.3 与 3.11 均通过）
- 无第三方运行时依赖；`pytest` 仅用于测试
- 若机器的 pytest 装有 `launch_testing` 等自动加载插件而报 `No module named 'yaml'`，
  设 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 即可（本套件不依赖任何 pytest 插件）
- 不联网：所有评审模型调用都是本地桩，不向境外发送任何数据

## 七、许可与保密

交付物中不出现客户名称；企业与人员全部虚构；可用于客户内部验收与集成，不对外分发。
