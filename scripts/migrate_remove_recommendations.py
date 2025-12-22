#!/usr/bin/env python3
"""
Database Migration: Remove obsolete 'recommendations' column
=============================================================

Removes the obsolete 'recommendations' column from the reviews table.
This field has been replaced by 'prompt_improvements' in session_quality_checks.

Usage:
    python scripts/migrate_remove_recommendations.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database_connection import get_db


async def run_migration():
    """Run the migration to remove recommendations column."""
    print("🔄 Starting migration: Remove 'recommendations' column from reviews table")
    print("="*80)

    db = await get_db()

    try:
        async with db.acquire() as conn:
            # Check if column exists first
            column_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'reviews'
                    AND column_name = 'recommendations'
                )
            """)

            if column_exists:
                print("✓ Found 'recommendations' column in reviews table")
                print("  Dropping column...")

                # Drop the column
                await conn.execute("""
                    ALTER TABLE reviews
                    DROP COLUMN recommendations
                """)

                print("✅ Successfully dropped 'recommendations' column")
            else:
                print("ℹ️  Column 'recommendations' does not exist (already removed or never existed)")

            # Verify the current schema
            print("\n📋 Current 'reviews' table columns:")
            columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'reviews'
                ORDER BY ordinal_position
            """)

            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"   - {col['column_name']:<25} {col['data_type']:<20} {nullable}")

            print("\n" + "="*80)
            print("✅ Migration completed successfully!")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(run_migration())
