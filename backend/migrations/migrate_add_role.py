"""
Quick migration script to add role column to users table.
Run: python migrate_add_role.py
"""
import asyncio
from sqlalchemy import text
from app.db.session import engine

async def migrate():
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'user'"
        ))
        print("✓ Added 'role' column to users table")
        
        # Update existing superusers to admin role
        await conn.execute(text(
            "UPDATE users SET role = 'admin' WHERE is_superuser = true AND (role IS NULL OR role = 'user')"
        ))
        print("✓ Updated existing superusers to 'admin' role")

if __name__ == "__main__":
    asyncio.run(migrate())
