# -*- coding: utf-8 -*-
"""AC2：用例文件 hash 变化后复核状态重置为待复核。"""
import uuid
from app.db import SessionLocal, EvalCase
from app import engine as eng
from tests.conftest import _h, REVIEWER_A, REVIEWER_B


def test_hash_change_resets_to_pending(client, case):
    url = "/api/eval/cases/%s/reviews" % case["case_id"]
    client.post(url, json={"verdict": "approve"}, headers=_h(REVIEWER_A))
    last = client.post(url, json={"verdict": "approve"}, headers=_h(REVIEWER_B)).json()
    assert last["review_status"] == "reviewed"

    # eval-sync 改文件 -> hash 变
    s = SessionLocal()
    try:
        c = s.get(EvalCase, uuid.UUID(case["case_id"]))
        c.content_hash = "f" * 64
        s.commit()
    finally:
        s.close()

    # 再来一条 approve，状态必须被重置为 pending（而非直接 reviewed）
    r = client.post(url, json={"verdict": "approve"}, headers=_h(REVIEWER_A)).json()
    assert r["review_status"] == "pending", r


def test_reset_rule_is_pure_function():
    # 纯函数层再钉一次：hash 不同 -> pending，hash 相同 -> 保持
    assert eng.reset_on_hash_change("aaa", "bbb", "reviewed") == "pending"
    assert eng.reset_on_hash_change("aaa", "aaa", "reviewed") == "reviewed"
    # 通过状态下 hash 不同也要回落
    st, _ = eng.decide_status([{"reviewer_id": "u1", "verdict": "approve"},
                               {"reviewer_id": "u2", "verdict": "approve"}],
                              current_hash="new", reviewed_hash="old")
    assert st == "pending"
