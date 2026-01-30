import asyncio
import logging

from app.db.base_class import Base
from app.db.session import engine
# Import all models so they are registered in Base
from app.models.user import User
from app.models.document import Document
from app.models.chat import ChatSession, ChatMessage
from app.models.audit_log import AuditLog
# Add other models here if any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_models():
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Uncomment to reset DB
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables created successfully")

if __name__ == "__main__":
    asyncio.run(init_models())
