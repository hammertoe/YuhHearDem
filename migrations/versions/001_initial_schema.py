"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-02-02 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("youtube_id", sa.String(20), nullable=False, unique=True),
        sa.Column("youtube_url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("chamber", sa.String(50), nullable=False),
        sa.Column("session_date", sa.DateTime(), nullable=False),
        sa.Column("sitting_number", sa.String(50)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("transcript", sa.JSON(), nullable=False),
        sa.Column("transcript_processed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("idx_videos_youtube_id", "videos", ["youtube_id"])
    op.create_index("idx_videos_date", "videos", ["session_date"])
    op.create_index("idx_videos_chamber", "videos", ["chamber"])

    op.create_table(
        "speakers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_id", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("title", sa.String(100)),
        sa.Column("role", sa.String(100)),
        sa.Column("chamber", sa.String(50)),
        sa.Column("aliases", sa.JSON(), server_default="[]"),
        sa.Column("pronoun", sa.String(10)),
        sa.Column("gender", sa.String(20)),
        sa.Column("first_seen_date", sa.DateTime()),
        sa.Column("metadata", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("idx_speakers_canonical_id", "speakers", ["canonical_id"])
    op.create_index(
        "idx_speakers_name",
        "speakers",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )

    op.create_table(
        "legislation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("legislation_id", sa.String(100), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("type", sa.String(50)),
        sa.Column("status", sa.String(50)),
        sa.Column("sponsors", sa.JSON(), server_default="[]"),
        sa.Column("chamber", sa.String(50)),
        sa.Column("parliament_id", sa.String(100)),
        sa.Column("pdf_url", sa.String()),
        sa.Column("description", sa.Text()),
        sa.Column("stages", sa.JSON(), server_default="[]"),
        sa.Column("scraped_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("idx_legislation_id", "legislation", ["legislation_id"])
    op.create_index(
        "idx_legislation_title",
        "legislation",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )

    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", sa.String(100), nullable=False, unique=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("aliases", sa.JSON(), server_default="[]"),
        sa.Column("description", sa.Text()),
        sa.Column("importance_score", sa.Float(), server_default="0"),
        sa.Column("legislation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("metadata", sa.JSON(), server_default="{}"),
        sa.Column("first_seen_date", sa.Date()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["legislation_id"], ["legislation.id"]),
    )
    op.create_index("idx_entities_entity_id", "entities", ["entity_id"])
    op.create_index("idx_entities_type", "entities", ["entity_type"])
    op.create_index(
        "idx_entities_name",
        "entities",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )

    op.create_table(
        "mentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agenda_item_index", sa.Integer()),
        sa.Column("sentence_index", sa.Integer()),
        sa.Column("timestamp_seconds", sa.Integer()),
        sa.Column("context", sa.Text()),
        sa.Column("bill_id", sa.String(100)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["entity_id"], ["entities.entity_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_mentions_entity_id", "mentions", ["entity_id"])
    op.create_index("idx_mentions_video_id", "mentions", ["video_id"])
    op.create_index("idx_mentions_timestamp", "mentions", ["timestamp_seconds"])

    op.create_table(
        "relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("target_id", sa.String(100), nullable=False),
        sa.Column("relation_type", sa.String(50), nullable=False),
        sa.Column("sentiment", sa.String(20)),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("video_id", postgresql.UUID(as_uuid=True)),
        sa.Column("timestamp_seconds", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["source_id"], ["entities.entity_id"]),
        sa.ForeignKeyConstraint(["target_id"], ["entities.entity_id"]),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
    )
    op.create_index("idx_relationships_source", "relationships", ["source_id"])
    op.create_index("idx_relationships_target", "relationships", ["target_id"])
    op.create_index("idx_relationships_type", "relationships", ["relation_type"])

    op.create_table(
        "vector_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sentence_index", sa.Integer(), nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("speaker_id", sa.String(100)),
        sa.Column("timestamp_seconds", sa.Integer()),
        sa.Column("metadata", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["speaker_id"], ["speakers.canonical_id"]),
    )
    op.create_index("idx_vector_embeddings_video_id", "vector_embeddings", ["video_id"])
    op.create_index(
        "idx_vector_embeddings_sentence", "vector_embeddings", ["sentence_index"]
    )
    op.execute(
        "CREATE INDEX idx_vector_embeddings_embedding ON vector_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.String(50), nullable=False, unique=True),
        sa.Column("user_id", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("last_updated", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("archived", sa.Boolean(), server_default=False),
        sa.Column("metadata", sa.JSON(), server_default="{}"),
    )
    op.create_index("idx_sessions_session_id", "sessions", ["session_id"])
    op.create_index("idx_sessions_user_id", "sessions", ["user_id"])
    op.create_index("idx_sessions_created", "sessions", ["created_at"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("structured_response", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_messages_session_id", "messages", ["session_id"])
    op.create_index("idx_messages_created", "messages", ["created_at"])

    op.create_table(
        "order_papers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pdf_path", sa.String(), nullable=False),
        sa.Column("pdf_hash", sa.String(), nullable=False),
        sa.Column("session_title", sa.String()),
        sa.Column("session_date", sa.DateTime()),
        sa.Column("sitting_number", sa.String(50)),
        sa.Column("chamber", sa.String(50)),
        sa.Column("speakers", sa.JSON(), nullable=False),
        sa.Column("agenda_items", sa.JSON(), nullable=False),
        sa.Column("parsed_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("video_id", "pdf_hash", name="unique_video_pdf_hash"),
    )
    op.create_index("idx_order_papers_video_id", "order_papers", ["video_id"])


def downgrade() -> None:
    op.drop_index("idx_order_papers_video_id", "order_papers")
    op.drop_table("order_papers")

    op.drop_index("idx_messages_created", "messages")
    op.drop_index("idx_messages_session_id", "messages")
    op.drop_table("messages")

    op.drop_index("idx_sessions_created", "sessions")
    op.drop_index("idx_sessions_user_id", "sessions")
    op.drop_index("idx_sessions_session_id", "sessions")
    op.drop_table("sessions")

    op.execute("DROP INDEX IF EXISTS idx_vector_embeddings_embedding")
    op.drop_index("idx_vector_embeddings_sentence", "vector_embeddings")
    op.drop_index("idx_vector_embeddings_video_id", "vector_embeddings")
    op.drop_table("vector_embeddings")

    op.drop_index("idx_relationships_type", "relationships")
    op.drop_index("idx_relationships_target", "relationships")
    op.drop_index("idx_relationships_source", "relationships")
    op.drop_table("relationships")

    op.drop_index("idx_mentions_timestamp", "mentions")
    op.drop_index("idx_mentions_video_id", "mentions")
    op.drop_index("idx_mentions_entity_id", "mentions")
    op.drop_table("mentions")

    op.drop_index("idx_entities_name", "entities")
    op.drop_index("idx_entities_type", "entities")
    op.drop_index("idx_entities_entity_id", "entities")
    op.drop_table("entities")

    op.drop_index("idx_legislation_title", "legislation")
    op.drop_index("idx_legislation_id", "legislation")
    op.drop_table("legislation")

    op.drop_index("idx_speakers_name", "speakers")
    op.drop_index("idx_speakers_canonical_id", "speakers")
    op.drop_table("speakers")

    op.drop_index("idx_videos_chamber", "videos")
    op.drop_index("idx_videos_date", "videos")
    op.drop_index("idx_videos_youtube_id", "videos")
    op.drop_table("videos")

    op.execute("DROP EXTENSION IF EXISTS vector")
