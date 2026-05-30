
import asyncio
from sqlalchemy import delete
from models.database import async_session
from models.roadmap import Roadmap
from services.cache_service import cache

async def main():
    # Clear Redis
    await cache.redis.flushdb()
    print('Redis cleared.')

    # Clear Roadmaps
    async with async_session() as session:
        await session.execute(delete(Roadmap))
        await session.commit()
    print('Roadmaps cleared.')

asyncio.run(main())

