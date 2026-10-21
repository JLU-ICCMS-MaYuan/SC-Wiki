"""统一业务、运维与就绪检查使用的 Qdrant 端点和认证。"""
from qdrant_client import QdrantClient
from backend.rag.config import settings


def create_qdrant_client() -> QdrantClient:
    options = {"api_key": settings.qdrant_api_key or None, "timeout": 5,
               "check_compatibility": False}
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url, **options)
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, **options)
