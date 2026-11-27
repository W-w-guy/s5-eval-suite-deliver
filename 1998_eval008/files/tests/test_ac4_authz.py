# -*- coding: utf-8 -*-
"""AC4：无评审权限的用户调用评审接口返回 403。"""
from tests.conftest import _h, NO_PERM, REVIEWER_A


def test_no_permission_review_403(client, case):
    url = "/api/eval/cases/%s/reviews" % case["case_id"]
    r = client.post(url, json={"verdict": "approve"},
                    headers=_h(NO_PERM, perms="eval.case.read"))
    assert r.status_code == 403, r.text
    assert "eval.case.review" in r.text


def test_empty_permissions_403(client, case):
    url = "/api/eval/cases/%s/reviews" % case["case_id"]
    r = client.post(url, json={"verdict": "approve"}, headers=_h(NO_PERM, perms=""))
    assert r.status_code == 403


def test_with_permission_200(client, case):
    url = "/api/eval/cases/%s/reviews" % case["case_id"]
    r = client.post(url, json={"verdict": "approve"}, headers=_h(REVIEWER_A))
    assert r.status_code == 200


def test_401_without_identity(client, case):
    url = "/api/eval/cases/%s/reviews" % case["case_id"]
    r = client.post(url, json={"verdict": "approve"})
    assert r.status_code == 401
