# -*- coding: utf-8 -*-
"""AC1：同一评审人重复 approve 不会让用例变为 reviewed，两名不同评审人 approve 后才变。"""
from tests.conftest import _h, REVIEWER_A, REVIEWER_B


def test_same_reviewer_twice_stays_pending(client, case):
    url = "/api/eval/cases/%s/reviews" % case["case_id"]
    r1 = client.post(url, json={"verdict": "approve"}, headers=_h(REVIEWER_A))
    assert r1.status_code == 200, r1.text
    assert r1.json()["review_status"] == "pending", r1.json()
    assert r1.json()["approvers"] == [REVIEWER_A]

    # 同一人第二次 approve —— 记录数变 2，但不同评审人数仍是 1
    r2 = client.post(url, json={"verdict": "approve"}, headers=_h(REVIEWER_A))
    assert r2.status_code == 200
    assert r2.json()["review_status"] == "pending", "同一人重复 approve 不得变 reviewed"
    assert len(r2.json()["approvers"]) == 1

    # 第三人再 approve 才够 2 名不同评审人
    r3 = client.post(url, json={"verdict": "approve"}, headers=_h(REVIEWER_B))
    assert r3.json()["review_status"] == "reviewed", r3.json()
    assert sorted(r3.json()["approvers"]) == sorted([REVIEWER_A, REVIEWER_B])


def test_two_distinct_reviewers_reach_reviewed(client, case):
    url = "/api/eval/cases/%s/reviews" % case["case_id"]
    a = client.post(url, json={"verdict": "approve"}, headers=_h(REVIEWER_A)).json()
    assert a["review_status"] == "pending"
    b = client.post(url, json={"verdict": "approve"}, headers=_h(REVIEWER_B)).json()
    assert b["review_status"] == "reviewed"
    assert b["required"] == 2


def test_revise_or_remove_sets_needs_change(client, case):
    url = "/api/eval/cases/%s/reviews" % case["case_id"]
    client.post(url, json={"verdict": "approve"}, headers=_h(REVIEWER_A))
    r = client.post(url, json={"verdict": "revise",
                               "point_comments": {"0": "要点1 需改写"},
                               "comment": "举例不足"},
                    headers=_h(REVIEWER_B)).json()
    assert r["review_status"] == "needs_change", r

    # remove 同样阻断，且即使已有 2 名 approve 之后再来 revise 也要降级
    client2 = client
    r2 = client2.post(url, json={"verdict": "remove"}, headers=_h(REVIEWER_A)).json()
    assert r2["review_status"] == "needs_change"


def test_remove_alone_blocks(client, case):
    """只有 remove、没有 revise 的场景——专门用来区分 BLOCKING 是否真的包含 remove。

    原先的用例先 revise 再 remove，状态早已是 needs_change，
    把 remove 从 BLOCKING 里拿掉也不会变红（变异 M2 漏抓就是因此）。
    """
    url = "/api/eval/cases/%s/reviews" % case["case_id"]
    r = client.post(url, json={"verdict": "remove",
                               "point_comments": {"1": "要点2 与要点1 重复"},
                               "comment": "该要点应删除"},
                    headers=_h(REVIEWER_A)).json()
    assert r["review_status"] == "needs_change", r

    # 即使随后有 2 名不同评审人 approve，只要 remove 记录还在，就不能回到 reviewed
    client.post(url, json={"verdict": "approve"}, headers=_h(REVIEWER_A))
    last = client.post(url, json={"verdict": "approve"}, headers=_h(REVIEWER_B)).json()
    assert last["review_status"] == "needs_change", last
