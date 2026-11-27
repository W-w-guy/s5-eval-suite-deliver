# -*- coding: utf-8 -*-
"""baseline：上游工单负责的评测套件/用例/运行表（本单只声明它们的既有形态）

真实集成时这三张表由上游迁移创建，本基线仅用于让本单的复现与验收可独立跑通。
Revision ID: 0000_baseline
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0000_baseline"
down_revision = None
branch_labels = None
depends_on = None

U = postgresql.UUID(as_uuid=True)
J = postgresql.JSONB


def upgrade():
    op.create_table(
        "eval_suite",
        sa.Column("id", U, primary_key=True),
        sa.Column("org_id", U, nullable=False),
        sa.Column("site_id", U, nullable=True),
        sa.Column("key", sa.String(120), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_by", U, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "eval_case",
        sa.Column("id", U, primary_key=True),
        sa.Column("org_id", U, nullable=False),
        sa.Column("site_id", U, nullable=True),
        sa.Column("suite_id", U, sa.ForeignKey("eval_suite.id"), nullable=False),
        sa.Column("case_key", sa.String(120), nullable=False),
        sa.Column("input_text", sa.Text, nullable=False),
        sa.Column("context", J, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("points", J, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False,
                  server_default=sa.text("'pending'")),
        sa.Column("reviewed_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_by", U, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("uq_eval_case_suite_key", "eval_case",
                    ["suite_id", "case_key"], unique=True)
    op.create_table(
        "eval_run",
        sa.Column("id", U, primary_key=True),
        sa.Column("org_id", U, nullable=False),
        sa.Column("case_id", U, sa.ForeignKey("eval_case.id"), nullable=False),
        sa.Column("output", J, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("hits", J, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("passed", sa.String(8), nullable=False, server_default=sa.text("'false'")),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )


def downgrade():
    op.drop_table("eval_run")
    op.drop_index("uq_eval_case_suite_key", table_name="eval_case")
    op.drop_table("eval_case")
    op.drop_table("eval_suite")
