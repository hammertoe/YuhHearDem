"""Add canonical speaker fields

Revision ID: 002
Revises: 001
Create Date: 2026-02-03
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    """Add canonical_id and aliases to speakers."""
    op.execute("ALTER TABLE speakers ADD COLUMN IF NOT EXISTS canonical_id VARCHAR(100)")
    op.execute(
        "ALTER TABLE speakers ADD COLUMN IF NOT EXISTS aliases JSON DEFAULT '[]'::json NOT NULL"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'speakers' AND column_name = 'metadata'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'speakers' AND column_name = 'meta_data'
            ) THEN
                ALTER TABLE speakers RENAME COLUMN metadata TO meta_data;
            END IF;
        END $$;
        """
    )
    op.execute("UPDATE speakers SET canonical_id = lower(name) WHERE canonical_id IS NULL")
    op.execute("ALTER TABLE speakers ALTER COLUMN canonical_id SET NOT NULL")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_speakers_canonical_id ON speakers (canonical_id)"
    )


def downgrade():
    """Remove canonical speaker fields."""
    op.execute("DROP INDEX IF EXISTS ix_speakers_canonical_id")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'speakers' AND column_name = 'meta_data'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'speakers' AND column_name = 'metadata'
            ) THEN
                ALTER TABLE speakers RENAME COLUMN meta_data TO metadata;
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE speakers DROP COLUMN IF EXISTS aliases")
    op.execute("ALTER TABLE speakers DROP COLUMN IF EXISTS canonical_id")
