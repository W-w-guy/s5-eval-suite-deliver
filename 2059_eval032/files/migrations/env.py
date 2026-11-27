# -*- coding: utf-8 -*-
"""Alembic 环境：URL 只从环境变量 DATABASE_URL 读（工单：配置只从环境变量读取）。"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

def _url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("缺少环境变量 DATABASE_URL")
    return url

config.set_main_option("sqlalchemy.url", _url())

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pkg.models import Base  # noqa: E402
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=_url(), target_metadata=target_metadata,
                      literal_binds=True, compare_type=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        {"sqlalchemy.url": _url()}, prefix="sqlalchemy.",
        poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
