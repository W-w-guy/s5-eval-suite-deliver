# -*- coding: utf-8 -*-
"""数据库接入：本地用 pgserver 起内嵌 PostgreSQL 16，生产读 DATABASE_URL。"""
from __future__ import annotations
import os
import uuid
from sqlalchemy import (Column, String, DateTime, Text, ForeignKey, text, Index)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from datetime import datetime, timezone

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class EvalSuite(Base):
    __tablename__ = "eval_suite"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    site_id = Column(UUID(as_uuid=True), nullable=True)
    key = Column(String(120), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class EvalCase(Base):
    __tablename__ = "eval_case"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    site_id = Column(UUID(as_uuid=True), nullable=True)
    suite_id = Column(UUID(as_uuid=True), ForeignKey("eval_suite.id"), nullable=False)
    case_key = Column(String(120), nullable=False)
    input_text = Column(Text, nullable=False)
    context = Column(JSONB, nullable=False, default=dict)
    points = Column(JSONB, nullable=False, default=list)      # 标准答案要点
    content_hash = Column(String(64), nullable=False)          # 用例文件 sha256
    review_status = Column(String(24), nullable=False, default="pending")
    reviewed_hash = Column(String(64), nullable=True)          # 上次通过时的 hash
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (Index("uq_eval_case_suite_key", "suite_id", "case_key", unique=True),)


class EvalCaseReview(Base):
    __tablename__ = "eval_case_review"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    site_id = Column(UUID(as_uuid=True), nullable=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("eval_case.id"), nullable=False)
    reviewer_id = Column(UUID(as_uuid=True), nullable=False)
    verdict = Column(String(16), nullable=False)               # approve / revise / remove
    point_comments = Column(JSONB, nullable=False, default=dict)
    comment = Column(Text, nullable=True)
    case_hash = Column(String(64), nullable=False)             # 评审时的用例 hash
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (Index("ix_eval_case_review_case", "case_id", "created_at"),)


class EvalRun(Base):
    __tablename__ = "eval_run"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    case_id = Column(UUID(as_uuid=True), ForeignKey("eval_case.id"), nullable=False)
    output = Column(JSONB, nullable=False, default=dict)
    hits = Column(JSONB, nullable=False, default=list)         # 每条要点命中布尔
    passed = Column(String(8), nullable=False, default="false")
    at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


_engine = None
_Session = None


def get_engine():
    global _engine, _Session
    if _engine is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            import pgserver
            d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".pgdata")
            srv = pgserver.get_server(os.path.abspath(d))
            url = srv.get_uri()
            os.environ["DATABASE_URL"] = url
        # SQLAlchemy 2 对 postgresql:// 默认选 psycopg(v3)；本机只有 psycopg2，
        # 所以显式补 +psycopg2，避免 ModuleNotFoundError: psycopg
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]
        _engine = create_engine(url, pool_pre_ping=True, future=True)
        _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def SessionLocal():
    get_engine()
    return _Session()


def server_version():
    with get_engine().connect() as c:
        return c.execute(text("SHOW server_version")).scalar()
