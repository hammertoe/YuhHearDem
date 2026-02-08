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

    print("\nCreating sessions table with new schema...")
    from models.session import Session

    async with engine.begin() as conn:
        await conn.run_sync(lambda: Session.metadata.create_all(conn))
        print("✓ Created sessions table with raw_transcript_json column")

    print("\nSessions table successfully recreated!")
    print("You can now run the ingestion script.")


if __name__ == "__main__":
    asyncio.run(recreate_sessions_table())
