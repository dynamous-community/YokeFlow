#!/usr/bin/env python3
"""Check if deep reviews exist and what data they contain."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database_connection import get_db


async def main():
    db = await get_db()

    try:
        async with db.acquire() as conn:
            # Count deep reviews
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM session_quality_checks WHERE check_type = 'deep'"
            )
            print(f"\nTotal deep reviews: {count}\n")

            if count > 0:
                # Get sample deep reviews
                result = await conn.fetch("""
                    SELECT
                        s.session_number,
                        p.name as project_name,
                        sqc.overall_rating,
                        sqc.review_text IS NOT NULL as has_text,
                        LENGTH(COALESCE(sqc.review_text, '')) as text_len,
                        sqc.prompt_improvements
                    FROM session_quality_checks sqc
                    JOIN sessions s ON sqc.session_id = s.id
                    JOIN projects p ON s.project_id = p.id
                    WHERE sqc.check_type = 'deep'
                    ORDER BY sqc.created_at DESC
                    LIMIT 5
                """)

                for row in result:
                    print(f"{row['project_name']} Session {row['session_number']}:")
                    print(f"  Rating: {row['overall_rating']}/10")
                    print(f"  Has review text: {row['has_text']} ({row['text_len']} chars)")

                    improvements = row['prompt_improvements']
                    if improvements:
                        print(f"  Prompt improvements: {len(improvements)}")
                        for i, imp in enumerate(improvements[:3], 1):
                            print(f"    {i}. {imp[:80]}...")
                    else:
                        print(f"  Prompt improvements: None")
                    print()

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
