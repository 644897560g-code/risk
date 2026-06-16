"""Add projects and project scoping.

Revision ID: 20260610_0004
Revises: 20260609_0003
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa


revision = "20260610_0004"
down_revision = "20260609_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("business_line", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("country", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("product", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_projects_status"), "projects", ["status"], unique=False)
    op.create_index(op.f("ix_projects_is_default"), "projects", ["is_default"], unique=False)

    op.execute(
        """
        INSERT INTO projects
            (id, name, business_line, country, product, description, status, is_default, created_at, updated_at)
        VALUES
            (1, '默认项目', '印尼现金贷', 'INDO', '短期现金贷', '系统初始化创建，用于承载迁移前已有任务和结果。', 'active', true, NOW(), NOW())
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute("SELECT setval(pg_get_serial_sequence('projects', 'id'), (SELECT max(id) FROM projects))")

    op.add_column("tasks", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_tasks_project_id"), "tasks", ["project_id"], unique=False)
    op.create_foreign_key("fk_tasks_project_id_projects", "tasks", "projects", ["project_id"], ["id"])
    op.execute("UPDATE tasks SET project_id = 1 WHERE project_id IS NULL")

    op.add_column("feature_versions", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_feature_versions_project_id"), "feature_versions", ["project_id"], unique=False)
    op.create_foreign_key(
        "fk_feature_versions_project_id_projects",
        "feature_versions",
        "projects",
        ["project_id"],
        ["id"],
    )
    op.execute("UPDATE feature_versions SET project_id = 1 WHERE project_id IS NULL")

    op.add_column("feature_metrics", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_feature_metrics_project_id"), "feature_metrics", ["project_id"], unique=False)
    op.create_foreign_key(
        "fk_feature_metrics_project_id_projects",
        "feature_metrics",
        "projects",
        ["project_id"],
        ["id"],
    )
    op.execute("UPDATE feature_metrics SET project_id = 1 WHERE project_id IS NULL")

    op.create_table(
        "project_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("template_db_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("selected_by", sa.Integer(), nullable=True),
        sa.Column("selected_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("config_override", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["selected_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["template_db_id"], ["templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "template_db_id", name="uq_project_templates_project_template"),
    )
    op.create_index(op.f("ix_project_templates_project_id"), "project_templates", ["project_id"], unique=False)
    op.create_index(op.f("ix_project_templates_template_db_id"), "project_templates", ["template_db_id"], unique=False)

    op.execute(
        """
        INSERT INTO project_templates
            (project_id, template_db_id, enabled, selected_at, created_at, updated_at)
        SELECT 1, id, true, NOW(), NOW(), NOW()
        FROM templates
        WHERE status = 'active'
        ON CONFLICT (project_id, template_db_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_project_templates_template_db_id"), table_name="project_templates")
    op.drop_index(op.f("ix_project_templates_project_id"), table_name="project_templates")
    op.drop_table("project_templates")

    op.drop_constraint("fk_feature_metrics_project_id_projects", "feature_metrics", type_="foreignkey")
    op.drop_index(op.f("ix_feature_metrics_project_id"), table_name="feature_metrics")
    op.drop_column("feature_metrics", "project_id")

    op.drop_constraint("fk_feature_versions_project_id_projects", "feature_versions", type_="foreignkey")
    op.drop_index(op.f("ix_feature_versions_project_id"), table_name="feature_versions")
    op.drop_column("feature_versions", "project_id")

    op.drop_constraint("fk_tasks_project_id_projects", "tasks", type_="foreignkey")
    op.drop_index(op.f("ix_tasks_project_id"), table_name="tasks")
    op.drop_column("tasks", "project_id")

    op.drop_index(op.f("ix_projects_is_default"), table_name="projects")
    op.drop_index(op.f("ix_projects_status"), table_name="projects")
    op.drop_table("projects")
