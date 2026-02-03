"""Add transcript segments table

Revision ID: 004
Revises: 003
Create Date: 2026-02-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

try:
    from pgvector.sqlalchemy import Vector

    VECTOR = Vector
except ImportError:
    VECTOR = None


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    """Create transcript segments table with embeddings."""
    if VECTOR:
        embedding_type = VECTOR(768)
    else:
        embedding_type = sa.JSON()

    op.create_table(
        "transcript_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("segment_id", sa.String(80), nullable=False),
        sa.Column("agenda_item_index", sa.Integer()),
        sa.Column("speech_block_index", sa.Integer()),
        sa.Column("segment_index", sa.Integer()),
        sa.Column("start_time_seconds", sa.Integer()),
        sa.Column("end_time_seconds", sa.Integer()),
        sa.Column("speaker_id", sa.String(100)),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(80)),
        sa.Column("embedding_version", sa.String(40)),
        sa.Column("embedding", embedding_type, nullable=False),
        sa.Column("meta_data", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["speaker_id"], ["speakers.canonical_id"]),
    )
    op.create_index("idx_transcript_segments_video_id", "transcript_segments", ["video_id"])
    op.create_index("idx_transcript_segments_segment_id", "transcript_segments", ["segment_id"])


def downgrade():
    """Drop transcript segments table."""
    op.drop_table("transcript_segments")
