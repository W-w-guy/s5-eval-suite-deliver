# -*- coding: utf-8 -*-
"""评测用例双人复核：eval_case_review 复核表

Revision ID: 0001_eval_case_review
Revises:
Create Date: 2026-11-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_eval_case_review"
down_revision = "0000_baseline"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "eval_case_review",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("eval_case.id"), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("point_comments", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("case_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("verdict in ('approve','revise','remove')",
                           name="ck_eval_case_review_verdict"),
    )
    op.create_index("ix_eval_case_review_case", "eval_case_review",
                    ["case_id", "created_at"])
    op.create_index("ix_eval_case_review_reviewer", "eval_case_review",
                    ["reviewer_id"])


def downgrade():
    op.drop_index("ix_eval_case_review_reviewer", table_name="eval_case_review")
    op.drop_index("ix_eval_case_review_case", table_name="eval_case_review")
    op.drop_table("eval_case_review")
