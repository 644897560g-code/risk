"""Template library schema.

Revision ID: 20260609_0002
Revises: 20260609_0001
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa


revision = "20260609_0002"
down_revision = "20260609_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "template_dimensions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dimension_code", sa.String(length=50), nullable=False),
        sa.Column("dimension_id", sa.String(length=20), nullable=True),
        sa.Column("dimension_name_cn", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dimension_id"),
    )
    op.create_index(
        op.f("ix_template_dimensions_dimension_code"),
        "template_dimensions",
        ["dimension_code"],
        unique=True,
    )

    op.create_table(
        "templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("template_id", sa.String(length=50), nullable=False),
        sa.Column("template_name", sa.String(length=100), nullable=False),
        sa.Column("template_name_cn", sa.String(length=100), nullable=False),
        sa.Column("dimension_id", sa.Integer(), nullable=False),
        sa.Column("source_channel", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("complexity", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("dsl", sa.Text(), nullable=False),
        sa.Column("dsl_description", sa.Text(), nullable=False),
        sa.Column("parameter_space", sa.JSON(), nullable=True),
        sa.Column("formula_template", sa.Text(), nullable=False),
        sa.Column("python_function", sa.String(length=100), nullable=False),
        sa.Column("python_module", sa.String(length=100), nullable=False),
        sa.Column("examples", sa.JSON(), nullable=True),
        sa.Column("quality_checks", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["dimension_id"], ["template_dimensions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_templates_template_id"), "templates", ["template_id"], unique=True)
    op.create_index("ix_templates_status", "templates", ["status"], unique=False)
    op.create_index("ix_templates_source_channel", "templates", ["source_channel"], unique=False)
    op.create_index("ix_templates_dimension_id", "templates", ["dimension_id"], unique=False)

    op.create_table(
        "template_review_histories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("template_db_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewer", sa.String(length=100), nullable=False),
        sa.Column("source_channel", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["template_db_id"], ["templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_template_review_histories_template_db_id",
        "template_review_histories",
        ["template_db_id"],
        unique=False,
    )
    op.create_index(
        "ix_template_review_histories_action",
        "template_review_histories",
        ["action"],
        unique=False,
    )

    op.create_table(
        "template_rejected_memories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("template_db_id", sa.Integer(), nullable=True),
        sa.Column("template_id", sa.String(length=50), nullable=False),
        sa.Column("template_name", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source_channel", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["template_db_id"], ["templates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_template_rejected_memories_template_id",
        "template_rejected_memories",
        ["template_id"],
        unique=False,
    )
    op.create_index(
        "ix_template_rejected_memories_created_at",
        "template_rejected_memories",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_template_rejected_memories_created_at", table_name="template_rejected_memories")
    op.drop_index("ix_template_rejected_memories_template_id", table_name="template_rejected_memories")
    op.drop_table("template_rejected_memories")
    op.drop_index("ix_template_review_histories_action", table_name="template_review_histories")
    op.drop_index("ix_template_review_histories_template_db_id", table_name="template_review_histories")
    op.drop_table("template_review_histories")
    op.drop_index("ix_templates_dimension_id", table_name="templates")
    op.drop_index("ix_templates_source_channel", table_name="templates")
    op.drop_index("ix_templates_status", table_name="templates")
    op.drop_index(op.f("ix_templates_template_id"), table_name="templates")
    op.drop_table("templates")
    op.drop_index(op.f("ix_template_dimensions_dimension_code"), table_name="template_dimensions")
    op.drop_table("template_dimensions")
