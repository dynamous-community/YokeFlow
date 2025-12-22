#!/usr/bin/env python3
"""Show the RECOMMENDATIONS section from a deep review."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database_connection import get_db


async def main():
    db = await get_db()

    try:
        async with db.acquire() as conn:
            # Get latest deep review
            result = await conn.fetchrow("""
                SELECT
                    s.session_number,
                    p.name as project_name,
                    sqc.overall_rating,
                    sqc.review_text,
                    sqc.prompt_improvements
                FROM session_quality_checks sqc
                JOIN sessions s ON sqc.session_id = s.id
                JOIN projects p ON s.project_id = p.id
                WHERE sqc.check_type = 'deep'
                  AND sqc.review_text IS NOT NULL
                ORDER BY sqc.created_at DESC
                LIMIT 1
            """)

            if not result:
                print("No deep reviews found")
                return

            print(f"\n{'='*80}")
            print(f"{result['project_name']} Session {result['session_number']} (Rating: {result['overall_rating']}/10)")
            print(f"{'='*80}\n")

            review = result['review_text']

            # Find RECOMMENDATIONS section
            if '## RECOMMENDATIONS' in review:
                idx = review.index('## RECOMMENDATIONS')
                # Find next ## section or end of file
                next_section = review.find('\n## ', idx + 10)
                if next_section == -1:
                    recommendations_section = review[idx:]
                else:
                    recommendations_section = review[idx:next_section]

                print("RECOMMENDATIONS SECTION FROM REVIEW:")
                print("-" * 80)
                print(recommendations_section)
                print("-" * 80)
            else:
                print("No RECOMMENDATIONS section found in review")
                # Show last 500 chars to see what's there
                print("\nLast 500 chars of review:")
                print(review[-500:])

            # Show what's stored in prompt_improvements
            print(f"\nSTORED IN prompt_improvements field:")
            print(f"Type: {type(result['prompt_improvements'])}")
            print(f"Value: {result['prompt_improvements']}")

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
