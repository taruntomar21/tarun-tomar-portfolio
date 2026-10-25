
"""Add project in-progress flag."""

from alembic import op
import sqlalchemy as sa

revision = "add_project_in_progress"
down_revision = "bad556326070"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "project",
        sa.Column(
            "is_in_progress",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade():
    op.drop_column("project", "is_in_progress")
