"""Query-time access to the pre-built vector index.

Kept separate from `build_index.py` (the ingestion path) so querying never
needs to re-embed the whole knowledge base — it just loads the JSON index
built by `build_index.py` and searches it.
"""
import os

from app.core.config import settings
from app.vectorstore.embeddings import get_embeddings
from app.vectorstore.store import SimpleVectorStore

_store: SimpleVectorStore | None = None


def get_vector_store() -> SimpleVectorStore:
    """Return the process-wide vector store, loading it from disk on first use."""
    global _store

    if _store is None:
        _store = SimpleVectorStore(
            persist_path=settings.vectorstore_path,
            embeddings=get_embeddings(),
        ).load()

    return _store


def index_exists() -> bool:
    return os.path.exists(settings.vectorstore_path)


def search_knowledge_base(query: str, k: int = 3) -> list[dict]:
    """Return the top-k most relevant knowledge chunks for `query`."""
    store = get_vector_store()
    return store.similarity_search(query, k=k)
