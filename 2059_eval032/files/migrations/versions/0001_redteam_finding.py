"""redteam_finding 与月度归档表

Revision ID: 0001
Revises:
Create Date: 2026-11-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # gen_random_uuid() 在 PG13+ 内置；PG16 无需扩展
    op.create_table(
        "redteam_finding",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("finding_no", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("tool", sa.String(64), nullable=False),
        sa.Column("technique", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(4), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("repro_steps", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("evidence_canary", sa.String(64), nullable=True),
        sa.Column("owner_role", sa.String(64), nullable=False),
        sa.Column("found_at", sa.Date(), nullable=False),
        sa.Column("confirmed_at", sa.Date(), nullable=True),
        sa.Column("fixed_at", sa.Date(), nullable=True),
        sa.Column("verified_run_id", sa.String(64), nullable=True),
        sa.Column("regression_case_key", sa.String(64), nullable=True),
        sa.Column("wont_fix_reason", sa.Text(), nullable=True),
        sa.Column("approved_by_role", sa.String(64), nullable=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("site_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("org_id", "finding_no", name="uq_rt_finding_no"),
    )
    op.create_index("ix_redteam_finding_tool", "redteam_finding", ["tool"])
    op.create_index("ix_redteam_finding_severity", "redteam_finding", ["severity"])
    op.create_index("ix_redteam_finding_status", "redteam_finding", ["status"])
    op.create_index("ix_redteam_finding_org", "redteam_finding", ["org_id"])
    op.create_index("ix_rt_finding_status_sev", "redteam_finding", ["status", "severity"])

    op.create_table(
        "redteam_monthly_archive",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("site_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("org_id", "month", name="uq_rt_month"),
    )
    op.create_index("ix_rt_month", "redteam_monthly_archive", ["month"])


def downgrade() -> None:
    op.drop_table("redteam_monthly_archive")
    op.drop_table("redteam_finding")
