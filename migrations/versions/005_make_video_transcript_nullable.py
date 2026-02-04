"""Make video transcript nullable

Revision ID: 005
Revises: 004
Create Date: 2026-02-04
"""

from alembic import op
import sqlalchemy as sa


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    """Allow NULL transcripts for deferred processing."""
    op.alter_column("videos", "transcript", existing_type=sa.JSON(), nullable=True)


def downgrade():
    """Revert transcripts to NOT NULL."""
    op.alter_column("videos", "transcript", existing_type=sa.JSON(), nullable=False)
