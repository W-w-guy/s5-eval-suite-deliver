# 执行器多轮调用的适配说明（#2037 kqa.multiturn）

本文件说的只有一件事：**怎么把 echo mock 换成你的真实被测系统**，接口保持不动。
换完之后 `python -m multiturn`、`verify_2037.py`、`pytest tests` 三条命令全部照旧。

## 一、唯一需要改的地方

`multiturn/__main__.py` 里的 `answer_turn(turn_text, history, facts, break_history)`。

签名必须保持：

```python
def answer_turn(turn_text: str, history: list, facts: dict, break_history: bool = False) -> str
```

| 参数 | 含义 |
|---|---|
| `turn_text` | 当前这一轮用户说的话（纯文本） |
| `history` | 之前的全部轮次，**时间正序**，元素为 `{"role": "user"\|"assistant", "text": str}`。调用本函数时**最后一条是上一轮 assistant 的回答**（不含本轮） |
| `facts` | 知识库索引，`{doc_id: {"doc_id","title","body":{小节名: 文本}}}`，仅 echo mock 用；接真实检索时可以不看它 |
| `break_history` | 破坏开关，真实实现里应当**忽略**（把它当 False），它只用于自证评测集有效 |

返回：**本轮回答的纯文本**。不要返回 dict、不要带角色前缀。

## 二、真实系统的接法（示意）

```python
import os, urllib.request, json

SUT_URL = os.environ["KQA_SUT_URL"]      # 被测服务的对话入口，只从环境变量读

def answer_turn(turn_text, history, facts, break_history=False):
    body = {"messages": [{"role": "user", "text": turn_text}] + history}
    req = urllib.request.Request(
        SUT_URL.rstrip("/") + "/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))["answer"]
```

要点：

1. **历史由 runner 维护并原样传出**，不要在被测端自己存会话 —— 否则 `--break-history` 就测不出东西（它正是靠“不传历史”来证明评测集考的是多轮）。
2. **一次评测会话不要复用服务端的会话缓存**。若被测系统有 session/context 概念，每组用例应新建会话（或带一个随机的 `session_id = case_id`）。
3. **必须容忍被测端报错**：超时/5xx 时返回空字符串即可，metrics 会把该轮判为不命中，不要让异常打断整轮评测。
4. 评审模型（若你的被测端内部调用）不得使用境外接口，地址同样从环境变量读。

## 三、每轮怎么被判定

runner 逐轮调用，`run_case()` 收集 `turn_outputs = {轮次索引: 回答}`，然后交给 `multiturn/metrics.py`：

| 指标 | 取哪一轮 | 口径 |
|---|---|---|
| `final_point_hit` | **最后一个 user 轮**的回答 | 该轮 `must_points`/`points` 的命中率 |
| `checkpoint_pass` | 所有带 `checkpoint: true` 的 **user 轮** | 这些轮次的 `must_points` 是否全部命中，比率 = 通过轮次数 / 检查点总数 |
| `forbidden` | **全部 user 轮**，含纠正轮本身 | 命中任一轮的 `forbidden_points` 即累计 1 次 |

注意两点（这两点踩过坑，见 README「五个必须先说清的点」）：

- 检查点挂在 **user 轮**上，不是 assistant 轮。挂在 assistant 轮会恒 0。
- 纠正类用例的**纠正轮自己**也纳入 forbidden 检查（`i >= last_correction`），不是只查它之后的轮次。

## 四、用例格式（cases.jsonl）

一行一条，字段：

```json
{"case_id": "MT-001", "kind": "coref|condition_change|topic_switch|correction",
 "turns": [{"role": "user", "text": "...", "checkpoint": true, "must_points": ["..."]},
           {"role": "assistant", "text": "（预置的上一轮答案）"},
           {"role": "user", "text": "..."}],
 "points": [{"desc": "...", "keyword_groups": [["..."]]}],
 "forbidden_points": [{"type": "stale_premise", "wrong_entity": "FQ-003",
                       "wrong_value": "...", "desc": "沿用被纠正的前提"}]}
```

被纠正的旧值必须 ≠ 纠正后的新值（生成器里有断言，防 forbidden 恒假阳性）。

## 五、换完之后怎么自查

```bash
python -m multiturn --tag real        # 指标应落在合理区间；若 final_point_hit 恒 1.0，说明没接上真实系统
python -m multiturn --break-history --tag bh
python -m multiturn --break-stale --tag bs
python verify_2037.py                 # 25 项 AC 断言
```

`--break-history` 必须让 `final_point_hit` 从 1.0 掉到 0.27 左右、`forbidden` 必须从 0 变成 8。
**如果换完真实系统后这两个开关仍然“有效”，说明评测链路没被你的实现绕过**；如果开关失效（指标不再变化），
说明你的实现把历史偷偷存在了服务端 —— 那就不是多轮评测了。
