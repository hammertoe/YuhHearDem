"""Initial database schema

Revision ID: 001
Revises:
Create Date: 2026-02-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create initial database tables"""

    # Videos table
    op.create_table(
        "videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("youtube_id", sa.String(20), nullable=False, unique=True),
        sa.Column("youtube_url", sa.String(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("chamber", sa.String(50), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("sitting_number", sa.String(50)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("transcript", sa.JSON(), nullable=False),
        sa.Column("transcript_processed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    # Order papers table
    op.create_table(
        "order_papers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pdf_path", sa.String(), nullable=False),
        sa.Column("pdf_hash", sa.String(), nullable=False),
        sa.Column("session_title", sa.String()),
        sa.Column("session_date", sa.Date()),
        sa.Column("sitting_number", sa.String(50)),
        sa.Column("chamber", sa.String(50)),
        sa.Column("speakers", sa.JSON(), nullable=False),
        sa.Column("agenda_items", sa.JSON(), nullable=False),
        sa.Column("parsed_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_unique_constraint("unique_video_pdf_hash", "order_papers", ["video_id", "pdf_hash"])

    # Speakers table
    op.create_table(
        "speakers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("title", sa.String(100)),
        sa.Column("role", sa.String(100)),
        sa.Column("chamber", sa.String(50)),
        sa.Column("pronoun", sa.String(10)),
        sa.Column("gender", sa.String(20)),
        sa.Column("first_seen_date", sa.DateTime()),
        sa.Column("metadata", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index(
        "idx_speakers_name",
        "speakers",
        ["name"],
    )

    # Legislation table
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
    )
    op.create_index("idx_legislation_id", "legislation", ["legislation_id"])
    op.create_index("idx_legislation_title", "legislation", ["title"])

    # Entities table
    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("chamber", sa.String(50), nullable=False),
        sa.Column("first_seen_date", sa.DateTime()),
        sa.Column("metadata", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    # Relationships table
    op.create_table(
        "relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("relation_type", sa.String(50), nullable=False),
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

    # Vector embeddings table (commented out due to pgvector issues)
    # Note: vector_cosine_ops not available in current pgvector/pg16 version
    #
    # op.create_table(
    #     "vector_embeddings",
    #     sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    #     sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
    #     sa.Column("sentence_index", sa.Integer(), nullable=False),
    #     sa.Column("embedding", sa.ARRAY(sa.Float()), nullable=False),
    #     sa.Column("text", sa.Text(), nullable=False),
    #     sa.Column("speaker_id", sa.String(100)),
    #     sa.Column("timestamp_seconds", sa.Integer()),
    #     sa.Column("metadata", sa.JSON(), server_default="{}"),
    #     sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    #     sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
    #     sa.ForeignKeyConstraint(["speaker_id"], ["speakers.canonical_id"]),
    # )
    # op.create_index("idx_vector_embeddings_video_id", "vector_embeddings", ["video_id"])
    # op.create_index(
    #     "idx_vector_embeddings_sentence",
    #     "vector_embeddings",
    #     ["sentence_index"]
    # )
    # op.execute(
    #     "CREATE INDEX idx_vector_embeddings_embedding ON vector_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    # )

    # Sessions table
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.String(50), nullable=False, unique=True),
        sa.Column("user_id", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("last_updated", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("False")),
        sa.Column("metadata", sa.JSON(), server_default="{}"),
    )
    op.create_index("idx_sessions_session_id", "sessions", ["session_id"])
    op.create_index("idx_sessions_user_id", "sessions", ["user_id"])
    op.create_index("idx_sessions_created", "sessions", ["created_at"])

    # Messages table
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.String(50), nullable=False),
        sa.Column("user_id", sa.String(50), nullable=False),
        sa.Column("role", sa.String(20)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("idx_messages_session_id", "messages", ["session_id"])
    op.create_index("idx_messages_user_id", "messages", ["user_id"])

    # Mentions table
    op.create_table(
        "mentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True)),
        sa.Column("sentence_index", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("timestamp_seconds", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.entity_id"]),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
    )
    op.create_index("idx_mentions_entity_id", "mentions", ["entity_id"])
    op.create_index("idx_mentions_video_id", "mentions", ["video_id"])

    # Sentiment table
    op.create_table(
        "sentiment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True)),
        sa.Column("positive", sa.Float()),
        sa.Column("negative", sa.Float()),
        sa.Column("neutral", sa.Float()),
        sa.Column("timestamp_seconds", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.entity_id"]),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
    )
    op.create_index("idx_sentiment_entity_id", "sentiment", ["entity_id"])
    op.create_index("idx_sentiment_video_id", "sentiment", ["video_id"])


def downgrade():
    """Drop all tables"""
    op.drop_table("sentiment")
    op.drop_table("mentions")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("vector_embeddings")
    op.drop_table("relationships")
    op.drop_table("entities")
    op.drop_table("legislation")
    op.drop_table("speakers")
    op.drop_table("order_papers")
    op.drop_table("videos")
