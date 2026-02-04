"""Change video-paper relationship from 1:1 to 1:N

Revision ID: a7e54960ab31
Revises: 005
Create Date: 2026-02-04 12:48:49.377680

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7e54960ab31"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add order_paper_id column if not exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("videos")]

    if "order_paper_id" not in columns:
        op.add_column("videos", sa.Column("order_paper_id", sa.UUID(), nullable=True))

    # Create foreign key and index
    try:
        op.create_foreign_key(
            "fk_videos_order_paper_id",
            "videos",
            "order_papers",
            ["order_paper_id"],
            ["id"],
            ondelete="CASCADE",
        )
    except Exception:
        pass  # May already exist

    try:
        op.create_index("ix_videos_order_paper_id", "videos", ["order_paper_id"])
    except Exception:
        pass  # May already exist

    # Check if order_papers has video_id column (old schema)
    op_columns = [c["name"] for c in inspector.get_columns("order_papers")]

    if "video_id" in op_columns:
        # Migrate data from old to new relationship
        op.execute("""
            UPDATE videos
            SET order_paper_id = (
                SELECT op.id
                FROM order_papers op
                WHERE op.video_id = videos.id
                LIMIT 1
            )
            WHERE EXISTS (
                SELECT 1
                FROM order_papers op
                WHERE op.video_id = videos.id
            )
        """)

        # Drop old constraint and column
        try:
            op.drop_constraint("unique_video_pdf_hash", "order_papers", type_="unique")
        except Exception:
            pass

        op.drop_column("order_papers", "video_id")


def downgrade() -> None:
    op.add_column(
        "order_papers", sa.Column("video_id", sa.UUID(), autoincrement=False, nullable=True)
    )

    op.create_index("ix_order_papers_video_id", "order_papers", ["video_id"])

    op.create_foreign_key(
        "order_papers_video_id_fkey",
        "order_papers",
        "videos",
        ["video_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.execute("""
        UPDATE order_papers
        SET video_id = (
            SELECT MIN(v.id)
            FROM videos v
            WHERE v.order_paper_id = order_papers.id
        )
        WHERE EXISTS (
            SELECT 1
            FROM videos v
            WHERE v.order_paper_id = order_papers.id
        )
    """)

    op.create_unique_constraint("unique_video_pdf_hash", "order_papers", ["video_id", "pdf_hash"])

    op.drop_index("ix_videos_order_paper_id", table_name="videos")
    op.drop_constraint("fk_videos_order_paper_id", "videos", type_="foreignkey")
    op.drop_column("videos", "order_paper_id")
