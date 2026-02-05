"""Drop vector_embeddings and add critical GraphRAG indexes

Revision ID: 008
Revises: 007_merge_heads
Create Date: 2026-02-05

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, Sequence[str], None] = "007_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop redundant vector_embeddings table
    op.drop_table("vector_embeddings", if_exists=True)

    # Add composite indexes for relationship traversal
    op.create_index(
        "idx_relationships_source_target",
        "relationships",
        ["source_id", "target_id", "relation_type"],
    )
    op.create_index(
        "idx_relationships_target_source",
        "relationships",
        ["target_id", "source_id", "relation_type"],
    )

    # Add covering index for mention→segment joins
    op.create_index(
        "idx_mentions_segment_lookup", "mentions", ["segment_id", "entity_id", "video_id"]
    )

    # Add composite index for mention queries by entity
    op.create_index(
        "idx_mentions_entity_video", "mentions", ["entity_id", "video_id", "timestamp_seconds"]
    )

    # Add index for transcript segment queries by video and time
    op.create_index(
        "idx_segments_video_time",
        "transcript_segments",
        ["video_id", "start_time_seconds", "end_time_seconds"],
    )


def downgrade() -> None:
    # Remove indexes
    op.drop_index("idx_segments_video_time", table_name="transcript_segments")
    op.drop_index("idx_mentions_entity_video", table_name="mentions")
    op.drop_index("idx_mentions_segment_lookup", table_name="mentions")
    op.drop_index("idx_relationships_target_source", table_name="relationships")
    op.drop_index("idx_relationships_source_target", table_name="relationships")

    # Recreate vector_embeddings table (basic structure)
    op.create_table(
        "vector_embeddings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("video_id", sa.UUID(), nullable=False),
        sa.Column("sentence_index", sa.Integer(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("speaker_id", sa.String(100), nullable=True),
        sa.Column("timestamp_seconds", sa.Integer(), nullable=True),
        sa.Column("meta_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vector_embeddings_video_id", "vector_embeddings", ["video_id"])
    op.create_index("ix_vector_embeddings_sentence_index", "vector_embeddings", ["sentence_index"])
