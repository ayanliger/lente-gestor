# syntax=docker/dockerfile:1.7
# ============================================================================
# Imagem multi-stage para o backend FastAPI do Lente Gestor.
# - builder: instala dependências em /install para maximizar cache do Docker
# - runtime: imagem fina com só o necessário para rodar uvicorn/alembic/scripts
#
# A mesma imagem serve para:
#   - Cloud Run service (API)                → CMD padrão (uvicorn)
#   - Cloud Run Jobs (migrate-db, ingest-*)  → sobrescrevem o command
# ============================================================================

FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# build-essential cobre compilação de wheels que eventualmente faltem
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Instalação em --prefix para copiar só o conteúdo já resolvido ao runtime
COPY requirements.txt ./
RUN pip install --prefix=/install -r requirements.txt

# ============================================================================

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=8080

# Usuário não-root para Cloud Run
RUN useradd --create-home --shell /bin/bash --uid 1000 app

COPY --from=builder /install /usr/local

WORKDIR /app

# Copia o código da aplicação. scripts/ é necessário para os Cloud Run Jobs;
# alembic.ini + app/db/migrations/ são necessários para o job de migração.
COPY --chown=app:app app ./app
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app alembic.ini ./alembic.ini

USER app

EXPOSE 8080

# Cloud Run injeta a var PORT; precisamos usar sh -c para expansão.
# --workers 2 é conservador para 512Mi; aumentar se mudar o sizing.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2"]
