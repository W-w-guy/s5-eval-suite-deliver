# -*- coding: utf-8 -*-
"""引擎与会话。URL 只从环境变量 DATABASE_URL 读。

★ 本模块**不做 create_all**：建表权归 Alembic 迁移。
  两者并存时，买家按 README 先跑 pytest（create_all 建表）再 alembic upgrade
  会立刻撞 DuplicateTable —— 这个坑只在买家按文档顺序操作时才暴露。
"""
import contextlib
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_engine = None
_Session = None


def database_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "缺少环境变量 DATABASE_URL。例如：\n"
            "  export DATABASE_URL=postgresql+psycopg2://user:pass@127.0.0.1:5432/dbname")
    return url


def get_engine():
    global _engine, _Session
    if _engine is None:
        _engine = create_engine(database_url(), pool_pre_ping=True, future=True)
        _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


@contextlib.contextmanager
def get_session():
    get_engine()
    sess = _Session()
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()


def reset_schema():
    """DROP SCHEMA public CASCADE 后由 Alembic 重建。

    测试夹具与 seed 都走这里，保证「测的是迁移真正建出来的表」，
    而不是 ORM 声明里的表（否则 schema 漂移会被放过）。
    """
    from sqlalchemy import text
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    from alembic import command
    from alembic.config import Config
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(root, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(root, "migrations"))
    command.upgrade(cfg, "head")
