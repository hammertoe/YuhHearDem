"""Merge heads a7e54960ab31 and 006_add_community_tables

Revision ID: 007_merge_heads
Revises: a7e54960ab31, 006_add_community_tables
Create Date: 2026-02-04 18:30:00.000000

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic
revision: str = "007_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "a7e54960ab31",
    "006_add_community_tables",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge heads."""
    pass


def downgrade() -> None:
    """Unmerge heads."""
    pass
