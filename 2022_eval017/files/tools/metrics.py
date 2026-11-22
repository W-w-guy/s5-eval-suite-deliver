# -*- coding: utf-8 -*-
"""三项指标：pairwise F1（聚类）、分类准确率、NDCG@5（排序）。

全部手动实现、纯标准库、每个函数都带手算用例（见 tests/test_metrics.py）。

为什么聚类用 pairwise F1 而不是 ARI：本单的聚类是「哪些资讯是同一事件」，
本质是 pair 级判断；pairwise F1 能直接回答「同一事件的两篇有没有被分到一起」
与「不同事件有没有被误并」，而 ARI 会把噪声簇的规模也摊进分数，解释性差。
"""
import math
import re

CJK = re.compile(r"[\u4e00-\u9fa5]")
NUM = re.compile(r"\d+(?:\.\d+)?")


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def grams(s: str, n: int = 2) -> set:
    """字符 n-gram 集合（中文不用分词，避免词典依赖）。"""
    s = norm(s).lower()
    chars = CJK.findall(s)
    return {"".join(chars[i:i + n]) for i in range(len(chars) - n + 1)}


def jaccard(a: str, b: str) -> float:
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def text_sim(a: str, b: str) -> float:
    """两篇资讯是否像同一事件：字符二元组 Jaccard + 数字交集加成。

    数字加成是关键的：同一事件的多来源报道措辞不同、日期不同，
    但「1.2 亿元」「3400 万元」这类关键数字一定相同；
    而「标题相似但事件不同」的干扰项数字往往不同。
    """
    j = jaccard(a, b)
    na, nb = set(NUM.findall(norm(a))), set(NUM.findall(norm(b)))
    if na and nb:
        num = len(na & nb) / len(na | nb)
    else:
        num = 0.0
    return round(0.65 * j + 0.35 * num, 6)


# ---------------- 聚类：pairwise F1 ----------------
def pairs_of(clusters: dict) -> set:
    """{cluster_id: [news_id...]} -> 同组内所有无序 pair 的集合。"""
    out = set()
    for members in clusters.values():
        m = sorted(set(members))
        for i in range(len(m)):
            for j in range(i + 1, len(m)):
                out.add((m[i], m[j]))
    return out


def pairwise_f1(gold: dict, pred: dict) -> dict:
    """P/R/F1 + 误合并数 + 漏合并数。

    误合并（merge_errors）  = 预测同组但金标不同组  -> 把两件事说成一件事
    漏合并（split_errors）  = 金标同组但预测不同组  -> 一件事被拆成两件
    这两个数比 F1 更能说明问题性质，所以单独给。
    """
    gp, pp = pairs_of(gold), pairs_of(pred)
    tp = len(gp & pp)
    p = tp / len(pp) if pp else (1.0 if not gp else 0.0)
    r = tp / len(gp) if gp else (1.0 if not pp else 0.0)
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": round(p, 6), "recall": round(r, 6), "f1": round(f1, 6),
            "tp": tp, "gold_pairs": len(gp), "pred_pairs": len(pp),
            "merge_errors": len(pp - gp), "split_errors": len(gp - pp)}


# ---------------- 簇对齐（分类与排序必须先对齐 id 空间）----------------
def align_clusters(gold: dict, pred: dict) -> dict:
    """建立 pred 簇 -> gold 簇 的映射（按成员重叠最大贪心匹配）。

    为什么必须有这一步：预测簇与金标簇各自编号（P01 vs E01），
    直接拿 id 去比分类准确率会全错 —— 那样测出来的是「编号是否相同」，
    不是「分类对不对」。真实评测里这是最容易漏的一步。
    """
    g_members = {k: set(v) for k, v in gold.items()}
    p_members = {k: set(v) for k, v in pred.items()}
    overlap = []
    for pk, pv in p_members.items():
        for gk, gv in g_members.items():
            n = len(pv & gv)
            if n:
                overlap.append((n, pk, gk))
    overlap.sort(key=lambda x: (-x[0], x[1], x[2]))
    mapping, used_g = {}, set()
    for n, pk, gk in overlap:
        if pk in mapping or gk in used_g:
            continue
        mapping[pk] = gk
        used_g.add(gk)
    return mapping


# ---------------- 分类准确率 ----------------
def category_accuracy(gold: dict, pred: dict, mapping: dict | None = None) -> dict:
    """按簇比分类。pred 的类别先经 mapping 映射到 gold 簇 id 再比。

    分母 = 金标簇数（预测漏掉的簇记错），分子 = 类别一致的簇数。
    """
    mapping = mapping if mapping is not None else align_clusters(gold, {k: [] for k in pred})
    pred_by_gold = {}
    for pk, gk in mapping.items():
        if pk in pred:
            pred_by_gold[gk] = pred[pk]
    ok = tot = 0
    detail = []
    for cid, cat in gold.items():
        p = pred_by_gold.get(cid)
        if p is None:
            detail.append({"cluster": cid, "gold": cat, "pred": None, "ok": False})
            tot += 1
            continue
        tot += 1
        good = (p == cat)
        ok += 1 if good else 0
        detail.append({"cluster": cid, "gold": cat, "pred": p, "ok": good})
    return {"accuracy": round(ok / tot, 6) if tot else 0.0, "correct": ok, "total": tot,
            "detail": detail}


# ---------------- NDCG@5 ----------------
def ndcg_at_k(gold_rank: list, pred_rank: list, k: int = 5, gains=None) -> float:
    """NDCG@5。相关性取金标名次映射的增益（第 1 名最高）。

    gains 可显式给 {cluster_id: gain}；不给则用 len-i（线性递减）。
    指数增益 2^rel - 1：让「把第 1 名排到第 5」的惩罚明显大于「把第 4 排到第 5」。
    """
    k = min(k, len(gold_rank)) if gold_rank else k
    if not gold_rank:
        return 1.0 if not pred_rank else 0.0
    if gains is None:
        gains = {c: (len(gold_rank) - i) for i, c in enumerate(gold_rank)}
    def dcg(seq):
        s = 0.0
        for i, c in enumerate(seq[:k], 1):
            g = gains.get(c, 0)
            s += (2 ** g - 1) / math.log2(i + 1)
        return s
    ideal = dcg(gold_rank)
    if ideal == 0:
        return 0.0
    return round(dcg(pred_rank) / ideal, 6)


# ---------------- forbidden_points ----------------
def forbidden_same_event_twice(pred_rank: list) -> list:
    """同一事件在简报 Top5 里出现两次（重复条目）。"""
    seen, dup = set(), []
    for c in pred_rank:
        if c in seen:
            dup.append(c)
        seen.add(c)
    return dup


def forbidden_outside_context(pred_clusters: dict, context_ids: set) -> list:
    """引用了 context 之外的资讯。"""
    bad = []
    for cid, members in pred_clusters.items():
        for m in members:
            if m not in context_ids:
                bad.append({"cluster": cid, "news_id": m})
    return bad


THRESH = {"pairwise_f1": 0.80, "category_accuracy": 0.80, "ndcg_at_5": 0.80}
LABELS = {"pairwise_f1": "聚类 pairwise F1", "category_accuracy": "分类准确率",
          "ndcg_at_5": "排序 NDCG@5"}


def check(key: str, value: float) -> bool:
    return value >= THRESH[key]
