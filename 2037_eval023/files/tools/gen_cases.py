# -*- coding: utf-8 -*-
"""生成 30 组多轮对话用例（turns 格式），复用 EVAL-022 的虚构知识库夹具。

四类分布（严格按单子）：
  指代消解 8 组         —— 第 2 轮用「那个/它」指代第 1 轮提到的实体
  条件变更 8 组         —— 第 3 轮改条件（换批次/换区），后文必须按新条件
  话题切换后回原话题 6 组 —— 第 3 轮问别的，第 4 轮「回到刚才那个」
  用户纠正前提 8 组     —— 第 2 轮纠正第 1 轮的前提，后文必须按纠正后的来

每组 3–5 轮。检查点（checkpoint + must_points）设在中间关键轮，最后一轮按要点评分。

★ 纠正类必须把「被纠正的旧前提」写进 forbidden_points：AC3 要求
  「8 组纠正类对话都把被纠正前提写入 forbidden_points（脚本检查）」。
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTS = json.load(open(os.path.join(HERE, "data", "facts.json"), encoding="utf-8"))
OUT = os.path.join(HERE, "data", "cases.jsonl")

BY = {}
for f in FACTS:
    BY.setdefault(f["cat"], []).append(f)


# ★ 知识库 120 篇里，policy 与 service 各有 30 篇但只用了 10 个名称，
#   于是每个名称对应 3 篇不同文档 —— 「标题 -> 文档」不是一对一。
#   多轮指代类用例必须能唯一定位到某一篇（「《X》那它呢」），
#   否则断言会落在另一篇上（实测：日期差 10 天，3/30 组假失败）。
#
#   处理方式：生成一份**本套件专用的索引层** data/facts_mt.json，
#   把每篇标题改成「原标题 #doc_id」保证唯一；**上游 120 篇 md 文件一字不改**
#   （它们是 EVAL-022 的夹具，改了就破坏「复用」的前提）。
MT_FACTS = os.path.join(HERE, "data", "facts_mt.json")
_MT = None


def mt_facts():
    global _MT
    if _MT is None:
        if os.path.isfile(MT_FACTS):
            rows = json.load(open(MT_FACTS, encoding="utf-8"))
        else:
            rows = [dict(r) for r in FACTS]
            for r in rows:
                r["title_orig"] = r["title"]
                r["title"] = "%s #%s" % (r["title"], r["doc_id"])
            os.makedirs(os.path.dirname(MT_FACTS), exist_ok=True)
            json.dump(rows, open(MT_FACTS, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
        _MT = {r["doc_id"]: r for r in rows}
    return _MT


def pick(cat, i):
    """取文档（从唯一标题的索引层里取）。"""
    base_doc = BY[cat][i % len(BY[cat])]
    return mt_facts()[base_doc["doc_id"]]


def sec(doc, key, default=""):
    return doc["body"].get(key, default)


def build_coref(i):
    d = pick("space_rule", i * 2)
    return {
        "case_id": "MT-C%02d" % (i + 1), "kind": "coref", "kb_doc": d["doc_id"],
        "turns": [
            {"role": "user", "text": "介绍一下《%s》。" % d["title"]},
            {"role": "assistant", "text": "（模型回答）"},
            {"role": "user", "text": "那它周末开放吗？", "checkpoint": True,
             "must_points": [sec(d, "开放时间")]},
            {"role": "user", "text": "它一次能容纳多少人？"},
        ],
        # 最后一轮只问「容纳多少人」-> 答案要点只放容量。
        # （开放时间在上一轮已经作为 checkpoint 考过了，不重复计入最后一轮）
        "final_expect": {"answer_points": [sec(d, "容量")],
                         "resolved_entity": d["doc_id"]},
        "forbidden_points": [{"type": "wrong_entity", "desc": "把「它」解析成别的场地/房间"}],
        "source": "synthetic",
    }


def build_condition(i):
    d = pick("policy", i)
    d2 = pick("policy", i + 5)
    return {
        "case_id": "MT-N%02d" % (i + 1), "kind": "condition_change", "kb_doc": d["doc_id"],
        "turns": [
            {"role": "user", "text": "《%s》的申报截止是哪天？" % d["title"]},
            {"role": "assistant", "text": "（模型回答）"},
            {"role": "user", "text": "如果不是我们这个区，而是另一个区的批次呢？适用对象会不会变？",
             "checkpoint": True, "must_points": [sec(d, "适用对象")]},
            {"role": "user", "text": "那《%s》的申报截止和支持标准分别是什么？" % d2["title"]},
        ],
        "final_expect": {"answer_points": [sec(d2, "申报截止"), sec(d2, "支持标准")],
                         "condition_changed": True},
        "forbidden_points": [{"type": "stale_condition", "desc": "沿用变更前的条件作答"}],
        "source": "synthetic",
    }


def build_switch(i):
    d = pick("service", i)
    other = pick("faq", i)
    return {
        "case_id": "MT-S%02d" % (i + 1), "kind": "topic_switch", "kb_doc": d["doc_id"],
        "turns": [
            {"role": "user", "text": "《%s》的响应时效是多久？" % d["title"]},
            {"role": "assistant", "text": "（模型回答）"},
            # 检查点考「切到新话题后能否答对新话题」，所以 must_points 必须是 FAQ 的答复
            {"role": "user", "text": "顺便问一下，《%s》怎么答？" % other["title"],
             "checkpoint": True, "must_points": [sec(other, "答复")]},
            {"role": "user", "text": "回到刚才那个，它的收费标准是什么？"},
        ],
        "final_expect": {"answer_points": [sec(d, "收费标准")], "back_to": d["doc_id"]},
        "forbidden_points": [
            {"type": "topic_bleed",
             "desc": "把上一轮话题（%s）的答案混入当前回答" % other["doc_id"]}],
        "source": "synthetic",
    }


def build_correction(i):
    d1 = pick("space_rule", i)
    # ★ 必须用 +7 而不是 +5：AREAS 只有 5 个，i 与 i+5 会落到同一区域，
    #   两者的「开放时间」完全相同 -> stale_premise_value 检查出假阳性（实测踩过）。
    d2 = pick("space_rule", i + 7)
    wrong = d1["title"]
    return {
        "case_id": "MT-R%02d" % (i + 1), "kind": "correction", "kb_doc": d2["doc_id"],
        "turns": [
            {"role": "user", "text": "《%s》的开放时间是几点？" % wrong, "checkpoint": True,
             "must_points": [sec(d1, "开放时间")]},
            {"role": "assistant", "text": "（模型回答）"},
            {"role": "user", "text": "不是这个，我说的是《%s》，开放时间是多少？" % d2["title"]},
            {"role": "user", "text": "那它的开放时间和最多能容纳多少人分别是什么？"},
        ],
        "final_expect": {"answer_points": [sec(d2, "开放时间"), sec(d2, "容量")],
                         "corrected_to": d2["doc_id"]},
        "forbidden_points": [
            {"type": "stale_premise",
             "desc": "沿用被纠正的错误前提：继续按《%s》作答" % wrong,
             "wrong_entity": d1["doc_id"]},
            {"type": "stale_premise_value",
             "desc": "沿用被纠正前提的具体值：%s" % sec(d1, "开放时间"),
             "wrong_value": sec(d1, "开放时间")},
        ],
        "source": "synthetic",
    }


def main():
    cases = [build_coref(i) for i in range(8)]
    cases += [build_condition(i) for i in range(8)]
    cases += [build_switch(i) for i in range(6)]
    cases += [build_correction(i) for i in range(8)]
    # 统一 4 轮（单子要求 3–5 轮）。
    # ★ 不要用「裁轮」制造多样性：裁掉的往往是最后一轮评分轮，
    #   会让 final_expect 与最后一问不匹配（实测 16/30 组假失败）。
    assert len(cases) == 30, len(cases)
    for c in cases:
        assert 3 <= len(c["turns"]) <= 5, (c["case_id"], len(c["turns"]))
        # 每个用例必须有恰好一个检查点轮
        cps = [t for t in c["turns"] if t.get("checkpoint")]
        assert len(cps) >= 1, c["case_id"]
    with open(OUT, "w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n")
    from collections import Counter
    print("cases", len(cases), dict(Counter(c["kind"] for c in cases)))
    print("轮次分布", dict(Counter(len(c["turns"]) for c in cases)))
    corr = [c for c in cases if c["kind"] == "correction"]
    # 自证：纠正类的「旧值」必须真的不同于「纠正后文档」的值，否则 forbidden 检查恒假阳性
    same_val = []
    for c in corr:
        fb = [f for f in c["forbidden_points"] if f["type"] == "stale_premise_value"]
        if fb and fb[0].get("wrong_value") in (c["final_expect"]["answer_points"] or [""])[0]:
            same_val.append(c["case_id"])
    print("纠正类里旧值==新值的组（应为空）:", same_val)
    ok = all(any(f["type"].startswith("stale_premise") for f in c["forbidden_points"])
             for c in corr)
    print("纠正类 %d 组，全部含 stale_premise forbidden: %s" % (len(corr), ok))


if __name__ == "__main__":
    main()
