# -*- coding: utf-8 -*-
"""生成 50 条评测用例（4 类分布严格按单子要求）。

分布：单文档事实 20 / 跨文档综合 12 / 数字与日期 10 / 同义改写 8。

每条用例的 gold_doc_ids 与 answer_points 都从同一份 facts.json 取，
所以「gold 文档存在」「答案要点能在文档里找到」是结构性的，不是事后核对出来的。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTS = json.load(open(os.path.join(HERE, "data", "facts.json"), encoding="utf-8"))
OUT = os.path.join(HERE, "data", "cases.jsonl")

BY = {}
for f in FACTS:
    BY.setdefault(f["cat"], []).append(f)


def pick(cat, i):
    return BY[cat][i % len(BY[cat])]


def pts(doc, keys, limit=5):
    """从文档里取指定小节，作为答案要点（原句，不是概括）。"""
    out = []
    for k in keys:
        if k in doc["body"] and len(out) < limit:
            out.append(doc["body"][k])
    return out


def build():
    cases = []

    # ---------- A. 单文档事实 20 条 ----------
    for i in range(20):
        d = pick("space_rule" if i % 2 == 0 else "service", i)
        # 问题必须把「作为答案要点的小节」全部问到。
        # 早期版本问题只问 2 项、答案要点却有 3 项，那第 3 项永远答不到 ——
        # 这是金标与问题不一致，属数据缺陷，不是被测工具的问题。
        if d["cat"] == "space_rule":
            q = "%s 的开放时间、容量与预约规则分别是什么？" % d["title"]
            keys = ["开放时间", "容量", "预约规则"]
        else:
            q = "%s 的响应时效、申请方式与覆盖范围是什么？" % d["title"]
            keys = ["响应时效", "申请方式", "覆盖范围"]
        cases.append({
            "case_id": "KQA-A%02d" % (i + 1), "type": "single_doc",
            "question": q, "gold_doc_ids": [d["doc_id"]],
            "answer_points": pts(d, keys), "source": "synthetic",
        })

    # ---------- B. 跨文档综合 12 条 ----------
    for i in range(12):
        a = pick("space_rule", i * 3)
        b = pick("service", i * 5)
        c = pick("faq", i * 7)
        q = ("关于「%s」和「%s」：前者的开放时间是什么，后者的响应时效与覆盖范围分别是什么？"
             % (a["title"], b["title"]))
        cases.append({
            "case_id": "KQA-B%02d" % (i + 1), "type": "multi_doc",
            "question": q, "gold_doc_ids": [a["doc_id"], b["doc_id"]],
            # 跨文档要点必须凑够 3 条：服务类文档有「响应时效」但没有「办理时限」，
            # 所以要按实际存在的小节补齐（不能假设小节名都存在）。
            "answer_points": (pts(a, ["开放时间"]) + pts(b, ["响应时效"])
                              + pts(b, ["覆盖范围", "申请方式"])[:1]
                              + pts(b, ["收费标准"])[:1])[:4],
            "source": "synthetic",
        })
        # 三段式跨文档：空间规则 + 服务 + FAQ
        if i % 3 == 0:
            cases[-1]["gold_doc_ids"] = [a["doc_id"], b["doc_id"], c["doc_id"]]
            cases[-1]["question"] = ("请综合「%s」「%s」「%s」回答：开放时间、响应时效、办理时限各是什么？"
                                     % (a["title"], b["title"], c["title"]))
            cases[-1]["answer_points"] = (pts(a, ["开放时间"]) + pts(b, ["响应时效"])
                                          + pts(c, ["办理时限"]))

    # ---------- C. 数字与日期 10 条 ----------
    for i in range(10):
        d = pick("policy", i * 3)
        q = "%s 的资助额度、申报截止日期与形式审查时限分别是多少？" % d["title"]
        cases.append({
            "case_id": "KQA-C%02d" % (i + 1), "type": "numeric_date",
            "question": q, "gold_doc_ids": [d["doc_id"]],
            "answer_points": pts(d, ["支持标准", "申报截止", "审核流程"]),
            "source": "synthetic",
        })

    # ---------- D. 同义改写提问 8 条 ----------
    # 同义改写：一个问题里用口语化说法问 3 个方面，答案要点也有 3 条。
    # 不采用「问 1 项、答案要点却有 3 项」的写法 —— 那样第 2/3 项永远答不到，
    # 是指标被数据设计压死，而非被测工具不行。
    PARA = [
        ("静音舱最晚能待到几点、大概能坐多少人、临时不用了要提前多久取消？",
         "space_rule", 0, ["开放时间", "容量", "预约规则"]),
        ("路演厅最晚能待到几点、能容纳多少人、爽约了会有什么后果？",
         "space_rule", 1, ["开放时间", "容量", "违约"]),
        ("会议室最早几点能进、能装多少人、订了不来要提前多久说？",
         "space_rule", 2, ["开放时间", "容量", "预约规则"]),
        ("我人不在现场能不能让别人代办、你们多久会回我、办这事要另外交钱吗？",
         "service", 3, ["覆盖范围", "响应时效", "收费标准"]),
        ("这项服务多久能回话、具体怎么申请、超出范围怎么算钱？",
         "service", 4, ["响应时效", "申请方式", "收费标准"]),
        ("找你们办事要等多久、通过什么渠道提、能给别人用吗？",
         "service", 5, ["响应时效", "申请方式", "覆盖范围"]),
        ("这个补贴最多能拿多少钱、什么时候截止、材料要交哪些？",
         "policy", 6, ["支持标准", "申报截止", "申报材料"]),
        ("钱什么时候能到、审批要多久、谁能申请？",
         "policy", 7, ["审核流程", "申报截止", "适用对象"]),
    ]
    for i, (q, cat, idx, keys) in enumerate(PARA):
        d = pick(cat, idx)
        ap = pts(d, keys)
        cases.append({
            "case_id": "KQA-D%02d" % (i + 1), "type": "paraphrase",
            "question": q, "gold_doc_ids": [d["doc_id"]],
            "answer_points": ap[:5], "source": "synthetic",
        })

    assert len(cases) == 50, len(cases)
    for c in cases:
        assert 1 <= len(c["gold_doc_ids"]) <= 3, c["case_id"]
        assert 3 <= len(c["answer_points"]) <= 5, (c["case_id"], len(c["answer_points"]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n")
    from collections import Counter
    print("cases", len(cases), dict(Counter(c["type"] for c in cases)))
    print("answer_points min/max", min(len(c["answer_points"]) for c in cases),
          max(len(c["answer_points"]) for c in cases))


if __name__ == "__main__":
    build()
