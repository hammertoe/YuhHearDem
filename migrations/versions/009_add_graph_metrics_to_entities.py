"""Add graph metrics columns to entities

Revision ID: 009
Revises: 008
Create Date: 2026-02-05

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, Sequence[str], None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add graph metrics columns
    op.add_column("entities", sa.Column("pagerank_score", sa.Float(), nullable=True))
    op.add_column("entities", sa.Column("degree_centrality", sa.Integer(), nullable=True))
    op.add_column("entities", sa.Column("betweenness_score", sa.Float(), nullable=True))
    op.add_column(
        "entities", sa.Column("relationship_count", sa.Integer(), nullable=True, server_default="0")
    )
    op.add_column(
        "entities", sa.Column("in_degree", sa.Integer(), nullable=True, server_default="0")
    )
    op.add_column(
        "entities", sa.Column("out_degree", sa.Integer(), nullable=True, server_default="0")
    )
    op.add_column("entities", sa.Column("metrics_updated_at", sa.DateTime(), nullable=True))

    # Add indexes for efficient querying
    op.create_index("ix_entities_pagerank", "entities", ["pagerank_score"])
    op.create_index("ix_entities_degree", "entities", ["degree_centrality"])


def downgrade() -> None:
    # Remove indexes
    op.drop_index("ix_entities_degree", table_name="entities")
    op.drop_index("ix_entities_pagerank", table_name="entities")

    # Remove columns
    op.drop_column("entities", "metrics_updated_at")
    op.drop_column("entities", "out_degree")
    op.drop_column("entities", "in_degree")
    op.drop_column("entities", "relationship_count")
    op.drop_column("entities", "betweenness_score")
    op.drop_column("entities", "degree_centrality")
    op.drop_column("entities", "pagerank_score")
