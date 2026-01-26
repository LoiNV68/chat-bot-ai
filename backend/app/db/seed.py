import asyncio
import logging
from sqlalchemy import select

from app.db.session import engine
from app.models.user import User
from app.core.security import get_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_users():
    # Use a session for ORM operations
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as session:
        # Check Admin
        stmt = select(User).where(User.email == "admin@gmail.com")
        result = await session.execute(stmt)
        admin_user = result.scalars().first()
        
        if not admin_user:
            logger.info("Creating Admin user...")
            pwd_hash = get_password_hash("123123")
            admin_user = User(
                email="admin@gmail.com",
                hashed_password=pwd_hash,
                full_name="System Administrator",
                is_superuser=True,
                is_active=True
            )
            session.add(admin_user)
        else:
            logger.info("Admin user already exists.")

        # Check Student
        stmt = select(User).where(User.email == "student@gmail.com")
        result = await session.execute(stmt)
        student_user = result.scalars().first()
        
        if not student_user:
            logger.info("Creating Student user...")
            student_user = User(
                email="student@gmail.com",
                hashed_password=get_password_hash("123123"),
                full_name="Nguyen Van A",
                is_superuser=False,
                is_active=True
            )
            session.add(student_user)
        else:
            logger.info("Student user already exists.")
        
        await session.commit()
    
    logger.info("Seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_users())
