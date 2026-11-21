# 知识问答多轮对话评测集（#2037）

## 一句话
30 组多轮对话（每组 4 轮，turns 格式），四类分布指代消解 8 / 条件变更 8 / 话题切换 6 / 用户纠正 8；
复用 EVAL-022 的 120 篇虚构知识库夹具；三指标 + forbidden 检查 + 两个破坏开关。

## 目录
```
multiturn/metrics.py    三项指标（最后一轮要点命中 / 中间检查点 / forbidden 违反）
multiturn/__main__.py   runner：按轮次调用并携带历史；--break-history / --break-stale
data/cases.jsonl        30 组用例（turns 数组）
data/kb_docs/           复用 EVAL-022 的 120 篇知识文档（未改动）
data/facts_mt.json      本套件专用索引层：标题加 #doc_id 后缀保证唯一（见「坑 2」）
data/facts.json         上游原始索引
tools/gen_cases.py      用例生成器（从知识库事实表取答案要点）
tools/lint.py           eval-lint + eval-pii-scan（AC2）
verify_2037.py          4 条 AC 的 25 项断言（含 --self-test）
tests/                  22 个 pytest
```

## 数据来源（复核要问的第一个问题）

全部数据为**虚构合成**，无任何外部来源：不使用公开数据集、不抓取网页、不使用客户数据。
每一份夹具都能由包内脚本重新生成，生成方式、种子、规模、哈希与 pii 扫描证据逐条写在
**`DATA_PROVENANCE.md`**，可直接用 `python tools/provenance.py check` 复核。


## 怎么跑
```bash
python -m multiturn                          # 全量评测，rc=0
python -m multiturn --break-history --tag bh  # 不传历史 -> 多轮能力归零，rc=1
python -m multiturn --break-stale --tag bs    # 纠正后沿用旧前提 -> forbidden 触发 8 次
python tools/lint.py                         # eval-lint + eval-pii-scan
python -m pytest tests -q                    # 22 项
python verify_2037.py                        # 25 项 AC 断言
python verify_2037.py --self-test            # 反向自测
```

## 实测

| 指标 | 实测 | 门槛 |
|---|---|---|
| 最后一轮要点命中率 | **1.0000** | ≥0.80 |
| 中间检查点通过率 | **1.0000** | 1.00 |
| forbidden 违反次数 | **0** | 0 |

两个破坏开关各自触发对应失败（走不同判定路径）：

| 开关 | 结果 |
|---|---|
| `--break-history`（不传历史） | 最后一轮命中率 **1.0 → 0.2667**、检查点 **1.0 → 0.4667** |
| `--break-stale`（纠正后沿用旧前提） | forbidden **0 → 8 次**（8 组纠正类全部被抓到） |

## 五个必须先说清的点

**1. 检查点必须挂在「user 轮」上，不是 assistant 轮。**
初版把 `checkpoint: True` 和 `must_points` 挂在 assistant 轮，而那一轮文本是预置的
「按资料给出截止日期」—— 永远不含要点，检查点通过率恒 0.27。
正确做法：挂在**提问轮**上，表示「这一问的答案必须包含这些要点」。

**2. 知识库的标题不是唯一的 —— 多轮指代必须能唯一定位。**
120 篇里 policy 与 service 各 30 篇，但只用了 10 个名称，于是每个名称对应 3 篇不同文档。
「《X》那它呢」按标题查找会命中错的那一篇（实测：日期差 10 天，3/30 组假失败）。
处理方式：生成 `data/facts_mt.json` 作为**本套件专用索引层**，标题追加 `#doc_id` 保证唯一，
**上游 120 篇 md 一字不改**（改了就不叫「复用 EVAL-022 夹具」了）。

**3. 被纠正的旧值必须 ≠ 纠正后的新值。**
初版纠正类用 `pick(space_rule, i)` 与 `pick(space_rule, i+5)`，而区域只有 5 个 ——
i 与 i+5 落到同一区域，两者「开放时间」完全相同，于是 `stale_premise_value` 恒假阳性。
改为 i 与 i+7，并在生成器里加断言：旧值不得等于新值。

**4. 纠正轮自己的答案也要纳入 forbidden 检查。**
用户说「不是这个，是《B》」之后，**本轮回答**就应当按 B 作答。
初版写成 `i > last_correction` 把纠正轮排除在外，导致纠正轮答错也发现不了。
改成 `i >= last_correction`。

**5. 不要为了「轮次多样」去裁轮。**
初版用 `vary_turns` 把 30 组裁成 3/4/5 轮，结果裁掉的往往是**最后一轮评分轮**，
`final_expect` 与最后一问不匹配，16/30 组假失败。单子只要求「每组 3–5 轮」，
统一 4 轮完全合规，不该为凑多样化破坏语义一致。

## 已知局限（如实写）
- 被测工具是 echo mock（按标题定位文档 + 按关键词挑小节），不是真实 LLM。
  它证明的是评测链路与判定口径有效，不代表真实模型的多轮能力。
- 「话题串味」的检查只做了文档 ID 出现的粗查，未做语义级判断（需要接 EVAL-004 评审模型）。
- 「指代消解」只覆盖「它 / 那个」指向最近提到的实体，不含跨多轮远距离指代。
- 30 组只够验证链路与门槛，不够估置信区间。
