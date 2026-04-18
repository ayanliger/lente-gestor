"""Entrypoint da aplicação FastAPI."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import api_router
from app.api.routes.chat import limiter as chat_limiter
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

# Rate limit — slowapi decora apenas as rotas que precisam, mas o handler
# de 429 e o middleware precisam ser registrados no app.
app.state.limiter = chat_limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: _rate_limit_response(exc),
)
app.add_middleware(SlowAPIMiddleware)


def _rate_limit_response(exc: RateLimitExceeded):
    """Resposta 429 em português, consistente com o resto da API."""
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=429,
        content={
            "detail": (
                "Muitas perguntas em pouco tempo. "
                "Tente novamente em alguns segundos."
            ),
            "limite": str(exc.detail),
        },
    )


app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Verifica se a aplicação está no ar."""
    return {"status": "ok", "version": "0.1.0"}
