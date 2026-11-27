# -*- coding: utf-8 -*-
"""另两个接口的契约测试：GET /api/eval/suites 与 GET /api/eval/cases/{id}。"""
from tests.conftest import _h, REVIEWER_A, REVIEWER_B


def test_list_suites_shape(client, case):
    r = client.get("/api/eval/suites", headers=_h(REVIEWER_A))
    assert r.status_code == 200
    items = r.json()["items"]
    assert items, "至少一个套件"
    it = [x for x in items if x["id"] == case["suite_id"]][0]
    for k in ("case_count", "reviewed_count", "latest_pass_rate"):
        assert k in it, "缺字段 " + k
    assert it["case_count"] == 1
    assert it["reviewed_count"] == 0


def test_suite_counts_after_review(client, case):
    url = "/api/eval/cases/%s/reviews" % case["case_id"]
    client.post(url, json={"verdict": "approve"}, headers=_h(REVIEWER_A))
    client.post(url, json={"verdict": "approve"}, headers=_h(REVIEWER_B))
    items = client.get("/api/eval/suites", headers=_h(REVIEWER_A)).json()["items"]
    it = [x for x in items if x["id"] == case["suite_id"]][0]
    assert it["reviewed_count"] == 1
    assert it["latest_pass_rate"] == 0.0  # 没有 run 记录


def test_get_case_payload(client, case):
    r = client.get("/api/eval/cases/%s" % case["case_id"], headers=_h(REVIEWER_A))
    assert r.status_code == 200
    d = r.json()
    for k in ("input", "context", "points", "recent_runs", "content_hash", "review_status"):
        assert k in d, "缺字段 " + k
    assert d["points"] == ["要点1", "要点2"]
    assert d["recent_runs"] == []
    assert d["review_status"] == "pending"


def test_get_case_404(client):
    r = client.get("/api/eval/cases/00000000-0000-0000-0000-000000000000",
                   headers=_h(REVIEWER_A))
    assert r.status_code == 404
