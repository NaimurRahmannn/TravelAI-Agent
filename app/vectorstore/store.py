"""A minimal, dependency-light vector store.

Rather than pulling in FAISS/Chroma (and their native build requirements),
this stores embeddings + text chunks as JSON on disk and does cosine
similarity in pure Python. That's plenty fast for a knowledge base of a
few hundred to a few thousand chunks, which is the realistic size for this
project's travel knowledge base.

Any object exposing `embed_documents(texts) -> list[list[float]]` and
`embed_query(text) -> list[float]` (LangChain's `Embeddings` interface)
can be passed in as the `embeddings` client, so this is easy to test with
a fake embedder and swap providers later.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Protocol


class EmbeddingsClient(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@dataclass
class VectorStoreEntry:
    text: str
    embedding: list[float]
    metadata: dict = field(default_factory=dict)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


class SimpleVectorStore:
    """In-memory vector index, persisted to a single JSON file."""

    def __init__(self, persist_path: str, embeddings: EmbeddingsClient):
        self.persist_path = persist_path
        self.embeddings = embeddings
        self._entries: list[VectorStoreEntry] = []

    # -- persistence -----------------------------------------------------

    def load(self) -> "SimpleVectorStore":
        if not os.path.exists(self.persist_path):
            self._entries = []
            return self

        with open(self.persist_path, encoding="utf-8") as f:
            raw = json.load(f)

        self._entries = [
            VectorStoreEntry(
                text=item["text"],
                embedding=item["embedding"],
                metadata=item.get("metadata", {}),
            )
            for item in raw
        ]
        return self

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.persist_path) or ".", exist_ok=True)

        payload = [
            {
                "text": entry.text,
                "embedding": entry.embedding,
                "metadata": entry.metadata,
            }
            for entry in self._entries
        ]

        with open(self.persist_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    # -- ingestion ---------------------------------------------------------

    def reset(self) -> None:
        self._entries = []

    def add_documents(
        self,
        texts: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        if not texts:
            return

        metadatas = metadatas or [{} for _ in texts]
        vectors = self.embeddings.embed_documents(texts)

        for text, vector, metadata in zip(texts, vectors, metadatas):
            self._entries.append(
                VectorStoreEntry(text=text, embedding=vector, metadata=metadata)
            )

    # -- querying ----------------------------------------------------------

    def similarity_search(self, query: str, k: int = 3) -> list[dict]:
        if not self._entries:
            return []

        query_vector = self.embeddings.embed_query(query)

        scored = [
            {
                "text": entry.text,
                "metadata": entry.metadata,
                "score": _cosine_similarity(query_vector, entry.embedding),
            }
            for entry in self._entries
        ]

        scored.sort(key=lambda item: item["score"], reverse=True)

        return scored[:k]

    def __len__(self) -> int:
        return len(self._entries)
