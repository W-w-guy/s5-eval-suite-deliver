# -*- coding: utf-8 -*-
"""三项指标各自的手算用例（期望值在注释里写出算式）。"""
import math

import pytest

import metrics as M


# ---------------- pairwise F1 ----------------
@pytest.mark.parametrize("gold,pred,f1,merge,split", [
    # 完全一致
    ({"A": [1, 2], "B": [3, 4]}, {"A": [1, 2], "B": [3, 4]}, 1.0, 0, 0),
    # 金标 2 对，预测把 4 篇并成 1 簇 = 6 对，tp=2
    # P=2/6=1/3, R=1 -> F1=2*(1/3)*1/(1/3+1)=0.5 ; 误合并 6-2=4
    ({"A": [1, 2], "B": [3, 4]}, {"A": [1, 2, 3, 4]}, 0.5, 4, 0),
    # 金标 1 簇 3 对，预测全拆开 = 0 对 -> P=1(空),R=0 -> F1=0 ; 漏合并 3
    ({"A": [1, 2, 3]}, {"A": [1], "B": [2], "C": [3]}, 0.0, 0, 3),
])
def test_pairwise_f1_handcalc(gold, pred, f1, merge, split):
    r = M.pairwise_f1(gold, pred)
    assert abs(r["f1"] - f1) < 1e-9, r
    assert r["merge_errors"] == merge
    assert r["split_errors"] == split


def test_pairwise_f1_counts_pairs_correctly():
    # 4 篇同簇 -> C(4,2)=6 对
    assert len(M.pairs_of({"X": [1, 2, 3, 4]})) == 6
    assert len(M.pairs_of({"X": [1, 2], "Y": [3, 4]})) == 2


# ---------------- 分类准确率（含簇对齐）----------------
def test_align_clusters_by_overlap():
    gold = {"G1": [1, 2], "G2": [3, 4]}
    pred = {"P9": [1, 2], "P8": [3, 4]}          # 编号完全不同
    assert M.align_clusters(gold, pred) == {"P9": "G1", "P8": "G2"}


def test_category_accuracy_after_alignment():
    """簇编号不同但内容一致 -> 分类准确率必须是 1.0（不是 0）。"""
    gold_c = {"G1": "政策", "G2": "融资"}
    pred_c = {"P7": "政策", "P3": "融资"}
    pred_members = {"P7": [1, 2], "P3": [3, 4]}
    gold_members = {"G1": [1, 2], "G2": [3, 4]}
    mp = M.align_clusters(gold_members, pred_members)
    r = M.category_accuracy(gold_c, pred_c, mp)
    assert r["accuracy"] == 1.0 and r["correct"] == 2


def test_category_accuracy_missed_cluster_counts_as_wrong():
    gold_c = {"G1": "政策", "G2": "融资"}
    pred_c = {"P1": "政策"}
    pred_members = {"P1": [1, 2]}
    gold_members = {"G1": [1, 2], "G2": [3, 4]}
    mp = M.align_clusters(gold_members, pred_members)
    r = M.category_accuracy(gold_c, pred_c, mp)
    assert r["accuracy"] == 0.5 and r["total"] == 2


# ---------------- NDCG@5 ----------------
def test_ndcg_identical_is_one():
    assert M.ndcg_at_k(["a", "b", "c"], ["a", "b", "c"]) == 1.0


def test_ndcg_handcalc_single_swap():
    """金标 [a,b]，预测 [b,a]。gains: a=2,b=1。
    ideal = (2^2-1)/1 + (2^1-1)/log2(3) = 3 + 1/1.585 = 3.6309
    pred  = (2^1-1)/1 + (2^2-1)/log2(3) = 1 + 3/log2(3) = 1 + 1.892789 = 2.892789
    ideal = 3 + 1/log2(3) = 3 + 0.630930 = 3.630930
    ndcg  = 2.892789/3.630930 = 0.7967075

    （最初我手算写成 0.796723，是 log2(3)=1.58496 的舍入误差累积；
      按 1/log2(3)=0.630930 重算得 0.796708，已更正。）
    """
    v = M.ndcg_at_k(["a", "b"], ["b", "a"])
    assert abs(v - 0.796708) < 1e-6, v


def test_ndcg_value_matches_manual_formula():
    """直接用 log2 现算一遍，确认实现没有额外加权的偏差。"""
    def dcg(seq, gains):
        return sum((2 ** gains.get(c, 0) - 1) / math.log2(i + 1)
                   for i, c in enumerate(seq, 1))
    gains = {"a": 2, "b": 1}
    expect = dcg(["b", "a"], gains) / dcg(["a", "b"], gains)
    # ndcg_at_k 返回值 round 到 6 位小数，容差要匹配这个精度（不是 1e-9）
    assert abs(M.ndcg_at_k(["a", "b"], ["b", "a"]) - expect) < 1e-6


def test_ndcg_unmapped_predictions_get_zero_gain():
    """预测里出现金标没有的簇（映射不到）-> 增益 0，不该被当成命中。"""
    v = M.ndcg_at_k(["a"], ["__unmapped__"])
    assert v == 0.0


def test_ndcg_empty_gold_with_empty_pred_is_one():
    assert M.ndcg_at_k([], []) == 1.0


# ---------------- 文本相似度 ----------------
def test_text_sim_same_number_diff_wording_high():
    a = "示例日报消息，示例云栈科技完成 A 轮融资，金额 1.2 亿元。"
    b = "据示例产业观察报道，示例云栈科技近日完成 A 轮融资，金额 1.2 亿元，细节已披露。"
    assert M.text_sim(a, b) > 0.5


def test_text_sim_different_numbers_lower():
    a = "示例云栈科技完成 A 轮融资，金额 1.2 亿元。"
    b = "示例海纳物流完成 B 轮融资，金额 2.6 亿元。"
    assert M.text_sim(a, b) < M.text_sim(a, "示例云栈科技完成 A 轮融资，金额 1.2 亿元。")


# ---------------- forbidden ----------------
def test_forbidden_same_event_twice():
    assert M.forbidden_same_event_twice(["E1", "E2", "E1"]) == ["E1"]
    assert M.forbidden_same_event_twice(["E1", "E2"]) == []


def test_forbidden_outside_context():
    bad = M.forbidden_outside_context({"P1": ["n1", "OUT-9"]}, {"n1", "n2"})
    assert bad == [{"cluster": "P1", "news_id": "OUT-9"}]
