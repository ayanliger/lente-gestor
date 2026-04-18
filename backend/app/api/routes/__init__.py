"""Agregador de rotas da API."""

from fastapi import APIRouter

from app.api.routes.chat import router as chat_router
from app.api.routes.contratacoes import router as contratacoes_router
from app.api.routes.contratos import router as contratos_router
from app.api.routes.fornecedores import router as fornecedores_router
from app.api.routes.itens_pca import router as itens_pca_router
from app.api.routes.municipio import router as municipio_router
from app.api.routes.orcamento import router as orcamento_router
from app.api.routes.orgaos import router as orgaos_router

api_router = APIRouter()
api_router.include_router(orgaos_router)
api_router.include_router(fornecedores_router)
api_router.include_router(contratacoes_router)
api_router.include_router(contratos_router)
api_router.include_router(itens_pca_router)
api_router.include_router(orcamento_router)
api_router.include_router(municipio_router)
api_router.include_router(chat_router)
