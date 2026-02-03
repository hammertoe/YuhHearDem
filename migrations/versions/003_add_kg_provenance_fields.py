"""Add knowledge graph provenance fields

Revision ID: 003
Revises: 002
Create Date: 2026-02-03
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    """Add provenance, subtype, and mention indexing fields."""
    op.execute("ALTER TABLE entities ADD COLUMN IF NOT EXISTS entity_subtype VARCHAR(50)")
    op.execute("ALTER TABLE entities ADD COLUMN IF NOT EXISTS entity_confidence FLOAT")
    op.execute("ALTER TABLE entities ADD COLUMN IF NOT EXISTS source VARCHAR(50)")
    op.execute("ALTER TABLE entities ADD COLUMN IF NOT EXISTS source_ref VARCHAR(200)")
    op.execute("ALTER TABLE entities ADD COLUMN IF NOT EXISTS speaker_canonical_id VARCHAR(100)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entities_speaker_canonical_id ON entities (speaker_canonical_id)"
    )

    op.execute("ALTER TABLE relationships ADD COLUMN IF NOT EXISTS source VARCHAR(50)")
    op.execute("ALTER TABLE relationships ADD COLUMN IF NOT EXISTS source_ref VARCHAR(200)")

    op.execute("ALTER TABLE mentions ADD COLUMN IF NOT EXISTS speech_block_index INTEGER")
    op.execute("ALTER TABLE mentions ADD COLUMN IF NOT EXISTS speaker_id VARCHAR(100)")
    op.execute("ALTER TABLE mentions ADD COLUMN IF NOT EXISTS speaker_canonical_id VARCHAR(100)")
    op.execute("ALTER TABLE mentions ADD COLUMN IF NOT EXISTS agenda_title TEXT")
    op.execute("ALTER TABLE mentions ADD COLUMN IF NOT EXISTS segment_id VARCHAR(80)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mentions_speaker_canonical_id ON mentions (speaker_canonical_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_mentions_segment_id ON mentions (segment_id)")


def downgrade():
    """Remove provenance, subtype, and mention indexing fields."""
    op.execute("DROP INDEX IF EXISTS ix_mentions_segment_id")
    op.execute("DROP INDEX IF EXISTS ix_mentions_speaker_canonical_id")
    op.execute("ALTER TABLE mentions DROP COLUMN IF EXISTS segment_id")
    op.execute("ALTER TABLE mentions DROP COLUMN IF EXISTS agenda_title")
    op.execute("ALTER TABLE mentions DROP COLUMN IF EXISTS speaker_canonical_id")
    op.execute("ALTER TABLE mentions DROP COLUMN IF EXISTS speaker_id")
    op.execute("ALTER TABLE mentions DROP COLUMN IF EXISTS speech_block_index")

    op.execute("ALTER TABLE relationships DROP COLUMN IF EXISTS source_ref")
    op.execute("ALTER TABLE relationships DROP COLUMN IF EXISTS source")

    op.execute("DROP INDEX IF EXISTS ix_entities_speaker_canonical_id")
    op.execute("ALTER TABLE entities DROP COLUMN IF EXISTS speaker_canonical_id")
    op.execute("ALTER TABLE entities DROP COLUMN IF EXISTS source_ref")
    op.execute("ALTER TABLE entities DROP COLUMN IF EXISTS source")
    op.execute("ALTER TABLE entities DROP COLUMN IF EXISTS entity_confidence")
    op.execute("ALTER TABLE entities DROP COLUMN IF EXISTS entity_subtype")
