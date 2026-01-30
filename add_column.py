import asyncio
import sys
import os

# Ensure backend directory is in path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def add_column():
    async with AsyncSessionLocal() as session:
        try:
            print("Adding file_path column to documents table...")
            await session.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_path VARCHAR"))
            await session.commit()
            print("Successfully added file_path column.")
        except Exception as e:
            print(f"Error: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(add_column())
