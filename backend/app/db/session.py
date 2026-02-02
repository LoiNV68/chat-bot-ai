from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# pool_pre_ping: Check connection health before using
# pool_recycle: Recycle connections after 300 seconds to prevent stale connections
engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI, 
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10,
    max_overflow=20
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
