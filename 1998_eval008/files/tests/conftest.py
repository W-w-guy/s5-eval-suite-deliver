# -*- coding: utf-8 -*-
import os, sys, uuid, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi.testclient import TestClient

ORG = uuid.UUID("11111111-1111-1111-1111-111111111111")
REVIEWER_A = "aaaaaaaa-0000-0000-0000-000000000001"
REVIEWER_B = "bbbbbbbb-0000-0000-0000-000000000002"
NO_PERM = "cccccccc-0000-0000-0000-000000000003"
REVIEW_PERMS = "eval.case.review,eval.case.read"


def _h(uid, perms=REVIEW_PERMS):
    return {"X-User-Id": uid, "X-Permissions": perms}


@pytest.fixture(scope="session")
def client():
    """整个会话开始前重置 schema 并按 alembic 迁移链建表。

    刻意不用 Base.metadata.create_all：那样测的是 ORM 声明的表，
    而不是迁移链真正建出来的表，schema 漂移会被悄悄放过。
    teardown 不 drop（每次会话开头自带 DROP SCHEMA，幂等），
    避免子进程把父进程依赖的库对象删掉。
    """
    from app.db import get_engine
    from app.main import app
    from app.schema import reset_and_migrate
    eng = get_engine()
    reset_and_migrate(eng)
    print("\n[PG] server_version =", _ver(eng))
    with TestClient(app) as c:
        yield c


def _ver(eng):
    from sqlalchemy import text
    with eng.connect() as c:
        return c.execute(text("SHOW server_version")).scalar()


@pytest.fixture()
def case(client):
    """新建一个 suite + case，每个用例独立，避免互相污染。"""
    from app.db import SessionLocal, EvalSuite, EvalCase
    s = SessionLocal()
    try:
        su = EvalSuite(id=uuid.uuid4(), org_id=ORG, key="suite-" + uuid.uuid4().hex[:8],
                       name="评测套件")
        s.add(su); s.flush()
        content = '{"input":"虚构问题","points":["要点1","要点2"]}'
        ca = EvalCase(id=uuid.uuid4(), org_id=ORG, suite_id=su.id,
                      case_key="case-" + uuid.uuid4().hex[:6],
                      input_text="虚构问题", context={"turns": 1},
                      points=["要点1", "要点2"],
                      content_hash=hashlib.sha256(content.encode()).hexdigest(),
                      review_status="pending")
        s.add(ca); s.commit()
        return {"case_id": str(ca.id), "suite_id": str(su.id), "hash": ca.content_hash}
    finally:
        s.close()
