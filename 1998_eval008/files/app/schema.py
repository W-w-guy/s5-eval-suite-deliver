# -*- coding: utf-8 -*-
"""Schema 的唯一入口：重置 public schema 后按 alembic 迁移链建表。

为什么不在 app 启动时 create_all：那会和 alembic 迁移打架——
两者都建表，谁先跑谁赢，后跑的报 DuplicateTable。
本单的验收明确要求 alembic upgrade/downgrade 可执行，所以建表权交给迁移。
"""
from __future__ import annotations
import os
from sqlalchemy import text


def _alembic_cfg():
    from alembic.config import Config
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(here, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "alembic"))
    return cfg


def reset_schema(engine=None):
    """DROP SCHEMA public CASCADE 后重建空 schema，幂等。"""
    from app.db import get_engine
    eng = engine or get_engine()
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    return eng


def upgrade_head(engine=None):
    from alembic import command
    eng = engine or reset_schema()
    upgrade_head.engine = eng
    command.upgrade(_alembic_cfg(), "head")
    return eng


def reset_and_migrate(engine=None):
    eng = reset_schema(engine)
    from alembic import command
    command.upgrade(_alembic_cfg(), "head")
    return eng
