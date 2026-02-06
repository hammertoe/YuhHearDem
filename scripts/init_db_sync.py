#!/usr/bin/env python3
import sys

sys.path.insert(0, ".")

from sqlalchemy import create_engine
from core.config import get_settings
from models import Base


def main():
    settings = get_settings()

    # Convert asyncpg URL to psycopg2 for synchronous SQLAlchemy
    sync_url = settings.database_url.replace("asyncpg", "psycopg2")
    print(f"Connecting to: {sync_url.split('@')[1] if '@' in sync_url else sync_url}")

    engine = create_engine(sync_url)

    print("Creating all tables...")
    Base.metadata.create_all(engine)

    table_count = len(Base.metadata.tables)
    print(f"Successfully created {table_count} tables:")
    for table_name in sorted(Base.metadata.tables.keys()):
        print(f"  - {table_name}")

    engine.dispose()
    print("\nDone!")


if __name__ == "__main__":
    main()
