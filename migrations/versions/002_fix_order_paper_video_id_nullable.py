"""Fix order_papers video_id constraint

Revision ID: 002
Revises: 001
Create Date: 2026-02-03

"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    """Make video_id nullable in order_papers"""
    # First drop the constraint
    op.drop_constraint("order_papers_video_id_not_null", "order_papers", type_="foreignkey")

    # Then alter the column to be nullable
    op.execute("ALTER TABLE order_papers ALTER COLUMN video_id DROP NOT NULL")


def downgrade():
    """Revert: Make video_id not null"""
    op.execute("ALTER TABLE order_papers ALTER COLUMN video_id SET NOT NULL")
    op.create_foreign_key(
        "fk_order_papers_video_id_videos",
        "order_papers",
        "video_id",
        "videos",
        "id",
        ondelete="CASCADE",
    )
