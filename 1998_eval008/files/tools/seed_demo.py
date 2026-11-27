# -*- coding: utf-8 -*-
"""给演示与截图准备一份虚构数据：1 个套件 / 3 个用例 / 若干复核与运行记录。

数据全部虚构，不含任何真实个人信息或企业信息。
运行： python tools/seed_demo.py [--reset]
"""
from __future__ import annotations
import os, sys, uuid, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import (get_engine, Base, SessionLocal, EvalSuite, EvalCase,
                    EvalCaseReview, EvalRun)

ORG = uuid.UUID("11111111-1111-1111-1111-111111111111")
A = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
B_ = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")

CASES = [
    {
        "key": "case-0001",
        "input": "虚构会员问：你们的产业对接活动下一次什么时候办？需要什么条件？",
        "context": {"turns": 1, "channel": "wechat"},
        "points": [
            "给出下一次活动的时间范围（不编造具体日期）",
            "说明参与条件：会员等级与所属行业",
            "提示可在小程序的活动页自助查询",
        ],
        "hits": [True, True, False],
        "status": "reviewed",
        "reviews": [(A, "approve"), (B_, "approve")],
    },
    {
        "key": "case-0002",
        "input": "虚构会员问：我上个月的积分怎么少了 200 分？",
        "context": {"turns": 2, "channel": "wechat"},
        "points": [
            "不透露其他会员的积分明细",
            "说明积分扣减的常见原因并给出查询入口",
            "无法确认时转人工，不猜测具体原因",
        ],
        "hits": [True, False, True],
        "status": "pending",
        "reviews": [(A, "approve")],
    },
    {
        "key": "case-0003",
        "input": "虚构会员问：能不能帮我把公司简介改成同行那家的？",
        "context": {"turns": 1, "channel": "web"},
        "points": [
            "拒绝代为改写他人资料",
            "说明资料修改需本人授权与实名核验",
        ],
        "hits": [True, True],
        "status": "needs_change",
        "reviews": [(A, "approve"), (B_, "revise")],
    },
]


def main(reset=False):
    from app.schema import upgrade_head
    eng = upgrade_head(get_engine())
    if reset:
        Base.metadata.drop_all(eng)
        Base.metadata.create_all(eng)
    s = SessionLocal()
    try:
        if s.query(EvalSuite).count():
            print("已有数据，跳过（加 --reset 重建）")
            return
        su = EvalSuite(id=uuid.uuid4(), org_id=ORG, key="member-qa-v3",
                       name="会员问询问答评测集 v3")
        s.add(su); s.flush()
        ids = {}
        for c in CASES:
            h = hashlib.sha256(json.dumps(
                {"i": c["input"], "p": c["points"]}, ensure_ascii=False).encode()).hexdigest()
            ca = EvalCase(id=uuid.uuid4(), org_id=ORG, suite_id=su.id,
                          case_key=c["key"], input_text=c["input"], context=c["context"],
                          points=c["points"], content_hash=h,
                          review_status=c["status"],
                          reviewed_hash=h if c["status"] == "reviewed" else None)
            s.add(ca); s.flush()
            ids[c["key"]] = str(ca.id)
            for who, verdict in c["reviews"]:
                s.add(EvalCaseReview(id=uuid.uuid4(), org_id=ORG, case_id=ca.id,
                                     reviewer_id=who, verdict=verdict,
                                     point_comments={}, comment=None, case_hash=h,
                                     created_by=who))
            s.add(EvalRun(id=uuid.uuid4(), org_id=ORG, case_id=ca.id,
                          output={"answer": "虚构回答"}, hits=c["hits"],
                          passed="true" if all(c["hits"]) else "false"))
        s.commit()
        print("seeded:", json.dumps(ids, ensure_ascii=False))
    finally:
        s.close()


if __name__ == "__main__":
    main(reset="--reset" in sys.argv)
