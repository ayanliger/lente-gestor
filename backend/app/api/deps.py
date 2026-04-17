"""Dependências compartilhadas para as rotas da API."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Injeta sessão async do banco de dados."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Depends(get_db)
