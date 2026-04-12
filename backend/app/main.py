"""Entrypoint da aplicação FastAPI."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Gerencia ciclo de vida da aplicação."""
    # Startup
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="Lente Gestor",
    description="Lente — API de inteligência, cruzamento de dados e accountability para gestão municipal",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — liberar frontend em desenvolvimento
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Verifica se a aplicação está no ar."""
    return {"status": "ok", "version": "0.1.0"}
