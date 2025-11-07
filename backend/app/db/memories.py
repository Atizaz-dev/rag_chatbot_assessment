from datetime import datetime
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://ai:ai@localhost:5432/ai")

engine = create_async_engine(DATABASE_URL, future=True, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Memory(BaseModel):
    id: int | None = None
    user_id: str
    memory_text: str
    inserted_at: datetime | None = None

async def add_memory(user_id: str, memory_text: str) -> Memory:
    async with AsyncSessionLocal() as session:
        stmt = text(
            "INSERT INTO user_memories (user_id, memory_text) VALUES (:user_id, :memory_text) RETURNING id, user_id, memory_text, inserted_at"
        )
        res = await session.execute(stmt, {"user_id": user_id, "memory_text": memory_text})
        await session.commit()
        row = res.first()
        return Memory(id=row.id, user_id=row.user_id, memory_text=row.memory_text, inserted_at=row.inserted_at)

async def get_user_memories(user_id: str, limit: int = 50) -> list[Memory]:
    async with AsyncSessionLocal() as session:
        stmt = text(
            "SELECT id, user_id, memory_text, inserted_at FROM user_memories WHERE user_id = :user_id ORDER BY inserted_at ASC LIMIT :limit"
        )
        res = await session.execute(stmt, {"user_id": user_id, "limit": limit})
        rows = res.fetchall()
        return [Memory(id=r.id, user_id=r.user_id, memory_text=r.memory_text, inserted_at=r.inserted_at) for r in rows]

async def clear_memories(user_id: str):
    async with AsyncSessionLocal() as session:
        stmt = text("DELETE FROM user_memories WHERE user_id = :user_id")
        await session.execute(stmt, {"user_id": user_id})
        await session.commit()
