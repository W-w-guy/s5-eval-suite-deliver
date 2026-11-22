# -*- coding: utf-8 -*-
"""AC4：每个指标计算函数都有至少 2 个【手算】用例。

「手算」= 期望值由人按定义算出并在注释里写出算式，不是把实现跑一遍贴结果。
用例命名统一 test_mNN_*，便于 verify 里逐个指标统计覆盖数（每个指标 >= 2）。
"""
import math

import pytest

from intel_eval import metrics as M


# ---------------- 1. 正文相似度 ----------------
@pytest.mark.parametrize("a,b,expect", [
    ("abc", "abc", 1.0),                    # LCS=3 -> 2*3/(3+3)=1
    ("abc", "abd", 2 / 3),                  # LCS=2 -> 2*2/(3+3)=0.666..
    ("", "abc", 0.0),                       # 一边为空 -> 0
    ("abc", "", 1.0 if False else 0.0),     # 同上，保持对称
])
def test_m01_body_similarity_handcalc(a, b, expect):
    assert abs(M.text_similarity(a, b) - expect) < 1e-9


def test_m01_ignores_whitespace_and_punct():
    # 归一化后 "a b c" == "abc"，标点被替换为空格
    assert M.text_similarity("a，b。c", "abc") == 1.0


# ---------------- 2. 发布日期准确率 ----------------
@pytest.mark.parametrize("pairs,expect", [
    ([("2026-01-01", "2026-01-01"), ("2026-01-02", "2026-01-03")], 0.5),     # 1/2
    ([("2026-01-01", "2026-01-01")], 1.0),                                   # 1/1
    ([("2026-01-01", "_abstain"), ("2026-02-02", "2026-02-02")], 1.0),       # _abstain 不计入分母 -> 1/1
    ([], 1.0),                                                               # 无样本 -> 1.0（不惩罚空集）
])
def test_m02_publish_date_accuracy_handcalc(pairs, expect):
    assert abs(M.m02_publish_date_accuracy(pairs) - expect) < 1e-9


# ---------------- 3. 归组 pairwise F1 与误合并 ----------------
@pytest.mark.parametrize("gold,pred,expect_f1,expect_merge", [
    ([[1, 2], [3, 4]], [[1, 2], [3, 4]], 1.0, 0),                 # 完全一致
    ([[1, 2], [3, 4]], [[1, 2, 3, 4]], 0.5, 4),                   # 金标2对，预测6对，tp=2 -> p=1/3,r=1,F1=0.5；多出4对
    ([[1, 2, 3]], [[1, 2], [3]], 2 / 3, 0),                       # 金标3对，预测1对，tp=1 -> p=1,r=1/3,F1=0.5? 见注释
])
def test_m03_group_f1_handcalc(gold, pred, expect_f1, expect_merge):
    g = [{"id": x} and set(x) for x in gold]
    p = [set(x) for x in pred]
    r = M.pairwise_f1(g, p)
    if expect_f1 == 2 / 3:
        # 手算：金标 3 对 {(1,2),(1,3),(2,3)}；预测 {(1,2)} -> p=1.0, r=1/3, F1=2*1*1/3/(1+1/3)=0.5
        assert abs(r["f1"] - 0.5) < 1e-9
    else:
        assert abs(r["f1"] - expect_f1) < 1e-9
    assert r["merge_errors"] == expect_merge


# ---------------- 4. policy_type 准确率 ----------------
@pytest.mark.parametrize("pairs,expect", [
    ([("event", "event"), ("policy_notice", "industry_news")], 0.5),
    ([("policy_notice", "policy_notice")], 1.0),
    ([("event", "_abstain")], 1.0),                              # _abstain 不计分母
])
def test_m04_policy_type_accuracy_handcalc(pairs, expect):
    assert abs(M.m04_policy_type_accuracy(pairs) - expect) < 1e-9


# ---------------- 5. 截止日期准确率 ----------------
@pytest.mark.parametrize("pairs,expect", [
    ([("2026-04-20", "2026-04-20"), ("2026-04-21", "2026-04-20")], 0.5),
    ([("_abstain", "_abstain")], 1.0),                           # 都不计分母 -> 1.0
    ([("2026-04-20", "2026-04-20"), ("_abstain", "_abstain")], 1.0),
])
def test_m05_deadline_accuracy_handcalc(pairs, expect):
    assert abs(M.m05_deadline_accuracy(pairs) - expect) < 1e-9


# ---------------- 6. 摘要关键事实覆盖率 ----------------
@pytest.mark.parametrize("pairs,expect", [
    ([("按投入 30% 支持，最高 200 万元", ["最高 200 万元"])], 1.0),      # 数字 200 命中
    ([("按投入 30% 支持，最高 200 万元", ["累计不超过 80 万元"])], 0.0),  # 80 未出现
    ([("摘要里提到 2026-04-20 截止", ["2026-04-20 截止"])], 1.0),        # 日期命中
    ([("摘要 A", ["_abstain"])], 1.0),                                  # _abstain 不计分母
])
def test_m06_key_fact_coverage_handcalc(pairs, expect):
    assert abs(M.m06_key_fact_coverage(pairs) - expect) < 1e-9


# ---------------- 7. 不一致数字/日期被标出比例 ----------------
@pytest.mark.parametrize("cases,expect", [
    # 摘要含 2026-01-01 但原文没有 -> 应标出 1 项；flagged 覆盖 -> 1.0
    ([{"summary": "截止 2026-01-01", "body": "截止 2026-02-02", "flagged": ["2026-01-01"]}], 1.0),
    # 同样的不一致但没标出 -> 0.0
    ([{"summary": "截止 2026-01-01", "body": "截止 2026-02-02", "flagged": []}], 0.0),
    # 摘要与原文完全一致 -> 无需标出 -> 1.0（空集不扣分）
    ([{"summary": "截止 2026-02-02", "body": "截止 2026-02-02", "flagged": []}], 1.0),
])
def test_m07_numeric_flagged_handcalc(cases, expect):
    assert abs(M.m07_numeric_mismatch_flagged(cases) - expect) < 1e-9


# ---------------- 8. 无原文链接进队列数 ----------------
@pytest.mark.parametrize("entries,expect", [
    ([{"has_original_link": False, "queued": True}], 1),         # 违规：进来了
    ([{"has_original_link": False, "queued": False}], 0),        # 正确：被丢弃
    ([{"has_original_link": True, "queued": True}], 0),          # 有链接的进队列是正常的
])
def test_m08_no_link_into_queue_handcalc(entries, expect):
    assert M.m08_no_link_into_queue(entries) == expect


# ---------------- 9. robots 违规数 ----------------
class _F:
    def __init__(self, n):
        self.n = n

    def robots_violations(self):
        return self.n


@pytest.mark.parametrize("n,expect", [(0, 0), (2, 2)])
def test_m09_robots_violations_handcalc(n, expect):
    assert M.m09_robots_violations(_F(n)) == expect


# ---------------- 10. 摘要含 URL 数 ----------------
@pytest.mark.parametrize("summaries,expect", [
    (["见 http://a.example/x 与 https://b.example/y"], 2),
    (["没有链接的一句话"], 0),
    (["www.c.example/z"], 1),
])
def test_m10_urls_in_summary_handcalc(summaries, expect):
    assert M.m10_urls_in_summary(summaries) == expect


# ---------------- 11. 联系方式残留 ----------------
@pytest.mark.parametrize("texts,expect", [
    (["联系电话 13800001111"], 1),                 # 手机号  # pii-scan:allow negative-fixture
    (["座机 010-12345678"], 1),                    # 座机
    (["邮箱 a@b.example"], 1),                     # 邮箱  # pii-scan:allow negative-fixture
    (["号码 010-XXXX-XXXX（占位）"], 0),            # 占位不算
    (["掩码 138****1111"], 0),                     # 掩码不算
])
def test_m11_pii_residue_handcalc(texts, expect):
    assert M.m11_pii_residue(texts) == expect


# ---------------- 辅助函数 ----------------
@pytest.mark.parametrize("gold,pred,k,expect", [
    ([1, 2, 3], [1, 2, 3], 5, 1.0),                # 完全一致 -> 1
    ([1, 2, 3], [3, 2, 1], 3, None),               # 反向，值与下面手算比
])
def test_ndcg_handcalc(gold, pred, k, expect):
    v = M.ndcg_at_k(gold, pred, k)
    if expect is not None:
        assert abs(v - expect) < 1e-9
    else:
        # 手算：rel = {1:3, 2:2, 3:1}
        # ideal: i=1 -> (2^3-1)/log2(2)=7/1=7; i=2 -> (2^2-1)/log2(3)=3/1.585=1.893; i=3 -> (2^1-1)/log2(4)=1/2=0.5
        # ideal = 7+1.8928+0.5 = 9.3928
        # pred [3,2,1]: (2^1-1)/1 + (2^2-1)/1.585 + (2^3-1)/2 = 1 + 1.8928 + 3.5 = 6.3928
        # ndcg = 6.392789/9.392789 = 0.680606（最初手算写成 0.680627，是 log2(3) 取值不准；已按实算更正）
        assert abs(v - 0.680606) < 1e-5, v


def test_desensitize_covers_three_kinds():
    from intel_eval.pipeline import desensitize
    out = desensitize("手机 13800001111 座机 010-12345678 邮箱 a@b.com")  # pii-scan:allow negative-fixture
    assert "13800001111" not in out  # pii-scan:allow negative-fixture
    assert "010-12345678" not in out
    assert "a@b.com" not in out  # pii-scan:allow negative-fixture
