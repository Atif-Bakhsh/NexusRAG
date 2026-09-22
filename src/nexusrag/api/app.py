from contextlib import asynccontextmanager
from functools import lru_cache
from threading import Lock

from fastapi import FastAPI, HTTPException

from nexusrag.config import Settings
from nexusrag.models import AskRequest
from nexusrag.service import QueryService

query_lock = Lock()


@lru_cache
def service() -> QueryService:
    return QueryService(Settings())


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    if service.cache_info().currsize:
        service().graph.close()
        service().repository.engine.dispose()
        service.cache_clear()


app = FastAPI(title="NexusRAG", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    try:
        svc = service()
        svc.repository.ping()
        active = svc.repository.active()
        svc.graph.ping()
        if not svc.graph.ready(active.version):
            raise RuntimeError("Graph unavailable")
        return {
            "status": "ready",
            "corpus_version": active.version,
            "graph_source": getattr(active, "configuration", {}).get("graph_source", "unknown"),
            "generation_configured": bool(svc.settings.openai_api_key.get_secret_value())
            and not svc.settings.disable_paid_api,
        }
    except Exception:
        raise HTTPException(
            503, "Databases or corpus not ready; run migrations and ingestion"
        ) from None


@app.get("/documents")
def documents():
    try:
        return service().repository.active().manifest
    except LookupError:
        raise HTTPException(503, "No ready corpus") from None


@app.get("/chunks/{chunk_id}")
def chunk(chunk_id: str):
    try:
        repo = service().repository
        chunks = repo.chunks(repo.active().version, [chunk_id])
        if not chunks:
            raise LookupError(chunk_id)
        return chunks[0]
    except LookupError:
        raise HTTPException(404, "Chunk not found in active corpus") from None


@app.post("/ask")
def ask(request: AskRequest):
    if not query_lock.acquire(blocking=False):
        raise HTTPException(429, "One query at a time; retry after the current query finishes")
    try:
        result = service().ask(request)
        if result["status"] == "failed":
            raise HTTPException(502, {"query_id": result["query_id"], "message": result["error"]})
        return result
    except LookupError:
        raise HTTPException(503, "No ready corpus") from None
    except ValueError:
        raise HTTPException(422, "Invalid question or document filter") from None
    finally:
        query_lock.release()


@app.get("/queries/{query_id}")
def query(query_id: str):
    try:
        return service().repository.get_query(query_id)
    except LookupError:
        raise HTTPException(404, "Query not found") from None


@app.get("/queries/{query_id}/trace")
def trace(query_id: str):
    return query(query_id)["trace"]
