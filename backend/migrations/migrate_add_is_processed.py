"""
Quick migration script to add is_processed column to documents table.
Run: python migrate_add_is_processed.py
"""
import asyncio
from sqlalchemy import text
from app.db.session import engine

async def migrate():
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_processed BOOLEAN DEFAULT FALSE"
        ))
        print("✓ Added 'is_processed' column to documents table")

if __name__ == "__main__":
    asyncio.run(migrate())
