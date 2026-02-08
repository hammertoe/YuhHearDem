"""Drop and recreate sessions table to add raw_transcript_json column."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import get_engine


async def recreate_sessions_table():
    """Drop and recreate sessions table with new schema."""
    engine = get_engine()

    print("Dropping sessions table...")
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS sessions CASCADE;"))
        print("✓ Dropped sessions table")

    print("\nDropping agenda_items table...")
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS agenda_items CASCADE;"))
        print("✓ Dropped agenda_items table")

    print("\nCreating sessions table with new schema...")
    from models.session import Session

    async with engine.begin() as conn:
        await conn.run_sync(Session.metadata.create_all)
        print("✓ Created sessions table with raw_transcript_json column")

    print("\nCreating agenda_items table with CASCADE on delete...")
    from models.agenda_item import AgendaItem

    async with engine.begin() as conn:
        await conn.run_sync(AgendaItem.metadata.create_all)
        print("✓ Created agenda_items table with CASCADE delete")

    print("\nSessions and agenda_items tables successfully recreated!")
    print("You can now run the ingestion script.")


if __name__ == "__main__":
    asyncio.run(recreate_sessions_table())
