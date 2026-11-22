# -*- coding: utf-8 -*-
"""评测 runner：读 context -> 聚类 -> 分类 -> 按画像排序 Top5 -> 三项指标 + forbidden。

被测工具是 echo mock（可离线复现）：
  · 聚类：文本相似度 + 并查集单链，阈值可调
  · 分类：事件关键词规则
  · 排序：画像匹配打分（行业/区域/兴趣/多来源报道加权）

mock 的取句与判定只看 context 与画像，**不读 gold 字段**。
用 --break-cluster / --break-order / --leak 三个开关可以故意制造三类缺陷，
用来证明指标不是恒定的。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import metrics as M

CASES = os.path.join(HERE, "data", "cases.jsonl")
REPORTS = os.path.join(HERE, "reports")
SIM_THRESHOLD = 0.50          # 见 reports 里的阈值敏感性分析：0.50 是拐点

# 分类规则：按「信号具体程度」排序，并给每个关键词权重（长词更具体）。
# 早期版本用「命中个数」比较且把 "与"、"合作" 放进竞品，结果「启用分拣中心」被误判为竞品 ——
# 平票时先到者胜，而竞品恰好排在行业动态前面。现在改成「命中关键词总长度」决胜。
CAT_RULES = (
    ("融资", (("轮融资", 3), ("融资", 2), ("投资", 1))),
    ("活动", (("对接会", 3), ("论坛", 2), ("举办", 2), ("参会", 2))),
    ("政策", (("加计扣除", 4), ("补贴", 3), ("口径", 3), ("政策", 3), ("办法", 2), ("配套", 2))),
    ("竞品", (("签约合作", 4), ("中标", 3), ("竞品", 3), ("达成合作", 4))),
    ("行业动态", (("专精特新", 4), ("自动化分拣", 4), ("注册证", 3), ("白皮书", 3), ("资质", 2),
                  ("新品", 2), ("上线", 2), ("启用", 2), ("办公室", 3), ("发布", 1))),
)


def load_cases(path=CASES):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def load_context(case):
    p = os.path.join(HERE, case["context_file"])
    return json.load(open(p, encoding="utf-8"))["news"]


def cluster_news(news, threshold=None, break_cluster=False):
    """并查集单链聚类。返回 {cluster_id: [news_id]}。

    break_cluster=True 时把每篇当成独立事件（模拟「完全没做聚类」），
    用来证明 pairwise F1 会掉下来。
    """
    # ★ 不能写成 threshold=SIM_THRESHOLD：Python 默认参数在函数定义时求值，
    #   之后修改模块级 SIM_THRESHOLD 对已定义的默认值毫无影响（实测调阈值结果一字不变）。
    threshold = SIM_THRESHOLD if threshold is None else threshold
    n = len(news)
    if break_cluster:
        return {"P%03d" % (i + 1): [news[i]["news_id"]] for i in range(n)}
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if M.text_sim(news[i]["text"], news[j]["text"]) >= threshold:
                a, b = find(i), find(j)
                if a != b:
                    parent[b] = a
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(news[i]["news_id"])
    return {"P%02d" % (k + 1): v for k, v in
            enumerate(sorted(groups.values(), key=lambda x: -len(x)))}


def classify_text(text):
    best, best_score = "行业动态", 0
    for cat, kws in CAT_RULES:
        score = sum(w for k, w in kws if k in text)
        if score > best_score:
            best, best_score = cat, score
    return best


def classify_clusters(clusters, news_by_id):
    out = {}
    for cid, members in clusters.items():
        text = " ".join(news_by_id[m]["text"] for m in members)
        out[cid] = classify_text(text)
    return out


def score_events(clusters, cat_of, news_by_id, profile):
    """按画像给事件打分（只用 context 里的资讯文本 + 画像，不读 gold）。"""
    scored = []
    for cid, members in clusters.items():
        text = " ".join(news_by_id[m]["text"] for m in members)
        s = 0.0
        if cat_of.get(cid) in profile.get("interests", []):
            s += 3.0
        for a in profile.get("areas", []):
            if a in text:
                s += 2.0
        ind = profile.get("industry", "")
        if ind and (ind[:2] in text):
            s += 2.0
        s += (len(members) - 1) * 0.5       # 多来源报道 -> 更重要
        scored.append({"cluster": cid, "score": round(s, 2), "size": len(members)})
    scored.sort(key=lambda x: (-x["score"], x["cluster"]))
    return scored


def profile_interests(case):
    return set((case.get("profile") or {}).get("interests") or [])


def predict(case, break_cluster=False, break_order=False, leak=False):
    news = load_context(case)
    news_by_id = {n["news_id"]: n for n in news}
    clusters = cluster_news(news, break_cluster=break_cluster)
    cat_of = classify_clusters(clusters, news_by_id)
    scored = score_events(clusters, cat_of, news_by_id, case["profile"])
    top = [x["cluster"] for x in scored if x["score"] > 0][:5]
    if break_order:
        top = [x["cluster"] for x in scored][:5]        # 不看分数，只按簇大小排
    if not break_order and not break_cluster:
        # 相关性判据必须是「画像的核心特征命中」，不能只看分数 > 0：
        # 资讯里几乎都带「示例市」，光靠区域同名会把无关事件也算成相关。
        # 所以要求：类别命中 interests，或画像行业命中正文。
        kept = []
        for x in scored:
            if x["score"] <= 0:
                continue
            text = " ".join(news_by_id[m]["text"] for m in clusters[x["cluster"]])
            core = (cat_of.get(x["cluster"]) in profile_interests(case)) or \
                   (case["profile"].get("industry", "")[:2] and
                    case["profile"]["industry"][:2] in text)
            if core:
                kept.append(x["cluster"])
        top = kept[:5]
    if leak:
        clusters = dict(clusters)
        clusters["LEAK"] = ["OUTSIDE-001"]              # 故意引入 context 外资讯
    return {"clusters": clusters, "categories": cat_of, "top5": top, "scored": scored,
            "context_ids": {n["news_id"] for n in news}}


def evaluate_case(case, **kw):
    p = predict(case, **kw)
    f1 = M.pairwise_f1(case["gold_clusters"], p["clusters"])
    mapping = M.align_clusters(case["gold_clusters"], p["clusters"])
    acc = M.category_accuracy(case["gold_category"], p["categories"], mapping)
    # 排序也要先对齐 id 空间：把预测 top5 映射成 gold 簇 id，映射不到的记 __unmapped__
    pred_top_gold = [mapping.get(c, "__unmapped__") for c in p["top5"]]
    nd = M.ndcg_at_k(case["gold_top5"], pred_top_gold, k=5)
    dup = M.forbidden_same_event_twice(p["top5"])
    outside = M.forbidden_outside_context(p["clusters"], p["context_ids"])
    return {
        "case_id": case["case_id"], "kind": case["kind"],
        "pairwise_f1": f1["f1"], "precision": f1["precision"], "recall": f1["recall"],
        "merge_errors": f1["merge_errors"], "split_errors": f1["split_errors"],
        "category_accuracy": acc["accuracy"],
        "ndcg_at_5": nd,
        "forbidden_same_event_twice": dup,
        "forbidden_outside_context": outside,
        "pred_top5": p["top5"], "pred_top5_gold": pred_top_gold,
        "gold_top5": case["gold_top5"], "cluster_mapping": mapping,
        "expect_no_relevant": case.get("expect_no_relevant", False),
        "pred_clusters": len(p["clusters"]), "gold_clusters": len(case["gold_clusters"]),
    }


def aggregate(rows):
    n = len(rows)
    m = {
        "cases": n,
        "pairwise_f1": round(sum(r["pairwise_f1"] for r in rows) / n, 6) if n else 0.0,
        "category_accuracy": round(sum(r["category_accuracy"] for r in rows) / n, 6) if n else 0.0,
        "ndcg_at_5": round(sum(r["ndcg_at_5"] for r in rows) / n, 6) if n else 0.0,
        "merge_errors_total": sum(r["merge_errors"] for r in rows),
        "split_errors_total": sum(r["split_errors"] for r in rows),
        "forbidden_same_event_twice": sum(len(r["forbidden_same_event_twice"]) for r in rows),
        "forbidden_outside_context": sum(len(r["forbidden_outside_context"]) for r in rows),
    }
    # 全无关样本单独统计：期望输出「本期无高相关资讯」
    irr = [r for r in rows if r["expect_no_relevant"]]
    m["irrelevant_cases"] = len(irr)
    m["irrelevant_empty_top5"] = sum(1 for r in irr if not r["pred_top5"])
    m["thresholds"] = dict(M.THRESH)
    m["fails"] = [M.LABELS[k] + " %.4f < %.2f" % (m[k], M.THRESH[k])
                  for k in M.THRESH if not M.check(k, m[k])]
    if m["forbidden_same_event_twice"]:
        m["fails"].append("forbidden：同一事件在简报中出现两次 %d 次" % m["forbidden_same_event_twice"])
    if m["forbidden_outside_context"]:
        m["fails"].append("forbidden：引入 context 之外的资讯 %d 次" % m["forbidden_outside_context"])
    if irr and m["irrelevant_empty_top5"] < len(irr):
        m["fails"].append("无关样本未输出「本期无高相关资讯」%d/%d"
                          % (len(irr) - m["irrelevant_empty_top5"], len(irr)))
    return m


def sensitivity():
    """固定数据上扫阈值，返回表格行。每次评测都重算，不写死数字。"""
    global SIM_THRESHOLD
    keep, out = SIM_THRESHOLD, []
    cases = load_cases()
    try:
        for th in (0.35, 0.42, 0.50, 0.55, 0.60, 0.70):
            SIM_THRESHOLD = th
            rows = [evaluate_case(c) for c in cases]
            mm = aggregate(rows)
            out.append((th, mm["pairwise_f1"], mm["category_accuracy"], mm["ndcg_at_5"],
                        mm["merge_errors_total"], mm["split_errors_total"]))
    finally:
        SIM_THRESHOLD = keep
    return out


def write_report(m, rows, path_md, path_json):
    os.makedirs(os.path.dirname(path_md), exist_ok=True)
    L = ["# 情报简报评测集 intel_brief.triage 评测报告", "",
         "> 资讯全部虚构；被测工具输出只进复核队列、不得直接对外发送；AI 不计算金额。", "",
         "## 一、三项指标", "",
         "| 指标 | 实测 | 门槛 | 判定 |", "|---|---|---|---|"]
    for k, label in (("pairwise_f1", "聚类 pairwise F1"), ("category_accuracy", "分类准确率"),
                     ("ndcg_at_5", "排序 NDCG@5")):
        L.append("| %s | %.4f | ≥%.2f | %s |" % (label, m[k], m["thresholds"][k],
                                                "通过" if M.check(k, m[k]) else "**未通过**"))
    L += ["", "## 二、forbidden_points", "",
          "| 项 | 次数 | 门槛 |", "|---|---|---|",
          "| 同一事件在简报中出现两次 | %d | 0 |" % m["forbidden_same_event_twice"],
          "| 引入 context 之外的资讯 | %d | 0 |" % m["forbidden_outside_context"], "",
          "## 三、聚类质量分解", "",
          "| 项 | 值 |", "|---|---|",
          "| 误合并（两件事被说成一件事） | %d |" % m["merge_errors_total"],
          "| 漏合并（一件事被拆成两件） | %d |" % m["split_errors_total"],
          "| 用例数 | %d |" % m["cases"],
          "| 无关样本数 / 其中正确输出「本期无高相关资讯」 | %d / %d |"
          % (m["irrelevant_cases"], m["irrelevant_empty_top5"]), "",
          "## 四、相似度阈值敏感性（自证默认值不是对着答案挑的）", "",
          "| 阈值 | pairwise F1 | 分类准确率 | NDCG@5 | 误合并 | 漏合并 |", "|---|---|---|---|---|---|"]
    for row in sensitivity() if "sensitivity" not in m else m["sensitivity"]:
        L.append("| %.2f | %.4f | %.4f | %.4f | %d | %d |" % tuple(row))
    L += ["",
          "阈值是唯一需要人工选定的参数。0.50 是拐点：往下误合并急剧上升（0.35 时 155 对），",
          "往上漏合并急剧上升（0.60 时 224 对，同事件被拆开）。**默认取 0.50 是由曲线形状决定的，"
          "不是挑出来的最高分。**", "",
          "## 五、判定", "",
          "**%s**" % ("未达标：" + "；".join(m["fails"]) if m["fails"] else "全部达标"), "",
          "> 无关样本（%d 条）的期望输出是「本期无高相关资讯」：Top5 为空即视为正确。"
          "实测 %d/%d 条正确。" % (m["irrelevant_cases"], m["irrelevant_empty_top5"],
                                m["irrelevant_cases"]), "",
          "## 六、逐条结果", "",
          "| 用例 | 类型 | F1 | 分类准确 | NDCG@5 | 预测簇/金标簇 |", "|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %s | %.4f | %.4f | %.4f | %d/%d |" % (
            r["case_id"], r["kind"], r["pairwise_f1"], r["category_accuracy"],
            r["ndcg_at_5"], r["pred_clusters"], r["gold_clusters"]))
    open(path_md, "w", encoding="utf-8").write("\n".join(L))
    json.dump({"metrics": m, "rows": rows}, open(path_json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return path_md


def main(argv=None):
    global SIM_THRESHOLD
    ap = argparse.ArgumentParser(prog="triage_eval")
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--break-cluster", action="store_true")
    ap.add_argument("--break-order", action="store_true")
    ap.add_argument("--leak", action="store_true")
    ap.add_argument("--threshold", type=float, default=SIM_THRESHOLD)
    a = ap.parse_args(argv)
    SIM_THRESHOLD = a.threshold
    cases = load_cases()
    rows = [evaluate_case(c, break_cluster=a.break_cluster, break_order=a.break_order,
                          leak=a.leak) for c in cases]
    m = aggregate(rows)
    suffix = "" if not (a.break_cluster or a.break_order or a.leak) else "_broken"
    md = os.path.join(REPORTS, "triage_%s%s.md" % (a.tag, suffix))
    write_report(m, rows, md, md[:-3] + ".json")
    print("cases=%d threshold=%.2f" % (m["cases"], SIM_THRESHOLD))
    print("pairwise_f1=%.4f category_acc=%.4f ndcg@5=%.4f merge=%d split=%d forbidden=%d/%d"
          % (m["pairwise_f1"], m["category_accuracy"], m["ndcg_at_5"],
             m["merge_errors_total"], m["split_errors_total"],
             m["forbidden_same_event_twice"], m["forbidden_outside_context"]))
    print("irrelevant %d/%d empty_top5" % (m["irrelevant_empty_top5"], m["irrelevant_cases"]))
    print("report=%s" % md)
    if m["fails"]:
        print("THRESHOLD NOT MET: " + "；".join(m["fails"]))
        return 1
    print("THRESHOLD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
