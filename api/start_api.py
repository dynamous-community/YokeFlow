#!/usr/bin/env python3
"""
Wrapper script to start the API server with proper configuration.
This ensures uvicorn can properly reload the module.
"""

import uvicorn
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Ensure we're in the correct directory (go to project root)
os.chdir(Path(__file__).parent.parent)

# Check if PostgreSQL is configured
from database_connection import is_postgresql_configured

if not is_postgresql_configured():
    print("\n" + "="*60)
    print("WARNING: PostgreSQL is not configured!")
    print("="*60)
    print("\nThe API will run with limited functionality.")
    print("To enable full functionality:")
    print("1. Start PostgreSQL: docker-compose up -d")
    print("2. Set DATABASE_URL in .env file")
    print("3. Initialize database: python scripts/init_database.py --docker")
    print("="*60 + "\n")

print("Starting API server on http://localhost:8000")
print("API documentation available at http://localhost:8000/docs")
print("\n⚠️  Auto-reload is DISABLED")
print("   You must manually restart the server to see code changes")
print("\nPress Ctrl+C to stop the server")
print("="*60 + "\n")

# Start the server WITHOUT auto-reload
# This prevents watchfiles from reloading when generations/ directory changes
uvicorn.run(
    "api.main:app",
    host="0.0.0.0",
    port=8000,
    reload=False,  # DISABLED: Must manually restart to see code changes
    log_level="error"
)
