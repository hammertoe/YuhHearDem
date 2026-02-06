#!/usr/bin/env python3
"""Reset database schema by dropping and recreating all tables"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import Base, get_engine


async def reset_database() -> None:
    """Drop and recreate all database tables"""
    engine = get_engine()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    print("Database reset complete")


if __name__ == "__main__":
    asyncio.run(reset_database())
