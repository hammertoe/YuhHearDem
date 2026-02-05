"""Add community tables for GraphRAG

Revision ID: 006_add_community_tables
Revises: 005
Create Date: 2026-02-04 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision: str = "006_add_community_tables"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create entity_communities table
    op.create_table(
        "entity_communities",
        sa.Column(
            "entity_id",
            sa.String(255),
            sa.ForeignKey("entities.entity_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("community_id", sa.Integer(), nullable=False),
        sa.Column("community_level", sa.Integer(), nullable=False, default=1),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("entity_id", "community_id"),
    )

    # Create indexes for efficient querying
    op.create_index(
        "idx_entity_communities_community_id",
        "entity_communities",
        ["community_id"],
    )
    op.create_index(
        "idx_entity_communities_level",
        "entity_communities",
        ["community_level"],
    )

    # Create community_summaries table
    op.create_table(
        "community_summaries",
        sa.Column("community_id", sa.Integer(), primary_key=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("key_entities", postgresql.JSONB(), nullable=False, default=list),
        sa.Column("member_count", sa.Integer(), nullable=False, default=0),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Create index for summary search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "idx_community_summaries_summary_gin",
        "community_summaries",
        ["summary"],
        postgresql_using="gin",
        postgresql_ops={"summary": "gin_trgm_ops"},
    )

    # Add GIN index for entity metadata (if not exists)
    op.create_index(
        "idx_entities_metadata_gin",
        "entities",
        ["meta_data"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_community_summaries_summary_gin")
    op.drop_index("idx_entity_communities_level")
    op.drop_index("idx_entity_communities_community_id")
    op.drop_index("idx_entities_metadata_gin")

    # Drop tables
    op.drop_table("community_summaries")
    op.drop_table("entity_communities")
