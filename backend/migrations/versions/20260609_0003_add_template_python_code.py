"""Add python_code to templates.

Revision ID: 20260609_0003
Revises: 20260609_0002
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa


revision = "20260609_0003"
down_revision = "20260609_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "templates",
        sa.Column("python_code", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("templates", "python_code", server_default=None)


def downgrade() -> None:
    op.drop_column("templates", "python_code")
