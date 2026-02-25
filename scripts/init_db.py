#!/usr/bin/env python3
"""Database initialization script.

Creates all database tables and ensures the database directory exists.

Usage:
    python scripts/init_db.py
"""

import asyncio
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.storage.database import init_db


async def main() -> None:
    """Initialize the database."""
    print("Reasoning-RAG Database Initialization")
    print("=" * 50)
    print(f"Database URL: {settings.database_url}")

    # Create data directory if needed
    if settings.database_url.startswith("sqlite"):
        # Extract path from sqlite URL
        db_path_str = settings.database_url.replace("sqlite+aiosqlite:///", "")
        db_path = Path(db_path_str)

        if db_path.exists():
            print(f"\nWarning: Database already exists at {db_path}")
            print("Existing tables will not be modified.")

        # Ensure parent directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Data directory: {db_path.parent} ✓")

    # Initialize database
    print("\nCreating database tables...")
    try:
        await init_db()
        print("✓ All tables created successfully")
        print("\nDatabase initialization complete!")
        print("\nNext steps:")
        print("  1. Add documents: Use the /api/documents/upload endpoint")
        print("  2. Seed test data: python scripts/seed_test_data.py")
        print("  3. Start server: uvicorn app.main:app --reload")
    except Exception as e:
        print(f"✗ Error during initialization: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
