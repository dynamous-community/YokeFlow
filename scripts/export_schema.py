#!/usr/bin/env python3
"""Export current database schema to a single consolidated file."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database_connection import get_db


async def export_schema():
    """Export the complete database schema."""
    db = await get_db()

    schema_parts = []

    try:
        async with db.acquire() as conn:
            # Get the CREATE TABLE statements for all tables
            tables = await conn.fetch("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)

            print(f"Found {len(tables)} tables")

            for table in tables:
                table_name = table['tablename']
                print(f"Exporting: {table_name}")

                # Get table definition
                result = await conn.fetchval("""
                    SELECT
                        'CREATE TABLE ' || quote_ident(tablename) || E' (\n' ||
                        string_agg(
                            '    ' || quote_ident(attname) || ' ' ||
                            pg_catalog.format_type(atttypid, atttypmod) ||
                            CASE WHEN attnotnull THEN ' NOT NULL' ELSE '' END ||
                            CASE WHEN atthasdef THEN ' DEFAULT ' || pg_get_expr(adbin, adrelid) ELSE '' END,
                            E',\n'
                            ORDER BY attnum
                        ) || E'\n);\n'
                    FROM pg_attribute a
                    JOIN pg_class c ON a.attrelid = c.oid
                    JOIN pg_namespace n ON c.relnamespace = n.oid
                    LEFT JOIN pg_attrdef d ON a.attrelid = d.adrelid AND a.attnum = d.adnum
                    WHERE n.nspname = 'public'
                    AND c.relname = $1
                    AND a.attnum > 0
                    AND NOT a.attisdropped
                    GROUP BY tablename, c.oid
                """, table_name)

                if result:
                    schema_parts.append(f"-- Table: {table_name}")
                    schema_parts.append(result)
                    schema_parts.append("")

            # Get all indexes
            indexes = await conn.fetch("""
                SELECT indexdef || ';' as indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND indexname NOT LIKE '%_pkey'
                ORDER BY tablename, indexname
            """)

            if indexes:
                schema_parts.append("-- Indexes")
                for idx in indexes:
                    schema_parts.append(idx['indexdef'])
                schema_parts.append("")

            # Get all views
            views = await conn.fetch("""
                SELECT
                    'CREATE OR REPLACE VIEW ' || quote_ident(viewname) || ' AS\n' ||
                    definition as viewdef
                FROM pg_views
                WHERE schemaname = 'public'
                ORDER BY viewname
            """)

            if views:
                schema_parts.append("-- Views")
                for view in views:
                    schema_parts.append(view['viewdef'])
                    schema_parts.append("")

            # Write to file
            output_file = Path(__file__).parent.parent / "schema" / "postgresql" / "schema.sql"
            schema_content = "\n".join(schema_parts)

            output_file.write_text(schema_content)
            print(f"\n✅ Schema exported to: {output_file}")
            print(f"   Size: {len(schema_content)} characters")

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(export_schema())
