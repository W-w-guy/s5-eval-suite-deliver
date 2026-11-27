# -*- coding: utf-8 -*-
"""SQLAlchemy 模型（对齐【统一技术约定】：UUID 主键 + org_id/site_id + 审计四字段 + 软删除）。

建表权归 Alembic 迁移，**不在 app 启动时 create_all** ——
两者并存会让买家「先 pytest 再 alembic upgrade」时撞 DuplicateTable。
"""
import os
import sys

from sqlalchemy import (Boolean, Column, Date, DateTime, Index, Integer, String,
                        Text, UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class AuditMixin(object):
    """审计四字段 + 软删除：工单统一约定（id/org_id/site_id/created_at/created_by/
    updated_at/deleted_at）。用 mixin 而不是 dict 解包 —— 类体里不能写 **kwargs。"""
    org_id = Column(String(64), nullable=False, index=True)
    site_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=text("now()"))
    created_by = Column(String(128), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=text("now()"))
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class RedteamFinding(Base, AuditMixin):
    __tablename__ = "redteam_finding"

    id = Column(PGUUID(as_uuid=False), primary_key=True,
                server_default=text("gen_random_uuid()"))
    finding_no = Column(String(16), nullable=False)
    title = Column(String(200), nullable=False)
    tool = Column(String(64), nullable=False, index=True)
    technique = Column(String(64), nullable=False)
    severity = Column(String(4), nullable=False, index=True)
    status = Column(String(16), nullable=False, index=True)
    repro_steps = Column(Text, nullable=False)
    evidence = Column(Text, nullable=False)          # 入库前已掩码
    evidence_canary = Column(String(64), nullable=True)  # 仅用于断言「已掩码」
    owner_role = Column(String(64), nullable=False)
    found_at = Column(Date, nullable=False)
    confirmed_at = Column(Date, nullable=True)
    fixed_at = Column(Date, nullable=True)
    verified_run_id = Column(String(64), nullable=True)
    regression_case_key = Column(String(64), nullable=True)
    wont_fix_reason = Column(Text, nullable=True)
    approved_by_role = Column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "finding_no", name="uq_rt_finding_no"),
        Index("ix_rt_finding_status_sev", "status", "severity"),
    )


class RedteamMonthlyArchive(Base, AuditMixin):
    """月度导出快照（供月报使用），保留每月导出时的三组清单。"""
    __tablename__ = "redteam_monthly_archive"

    id = Column(PGUUID(as_uuid=False), primary_key=True,
                server_default=text("gen_random_uuid()"))
    month = Column(String(7), nullable=False, index=True)
    payload_json = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "month", name="uq_rt_month"),
    )
