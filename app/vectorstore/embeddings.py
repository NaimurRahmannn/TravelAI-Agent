"""Embeddings client used for the RAG knowledge base.

Uses Google's Generative AI embedding model via `langchain-google-genai`,
which was already listed in requirements.txt (added ahead of this feature
being built) but previously unused anywhere in the codebase.
"""
from app.core.config import settings


def get_embeddings():
    """Return a configured `GoogleGenerativeAIEmbeddings` client.

    Requires `google_api_key` to be set in `.env`. Imported lazily so the
    rest of the app doesn't need `langchain-google-genai` installed unless
    the RAG feature is actually used.
    """
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    if not settings.google_api_key:
        raise ValueError(
            "google_api_key is not configured in .env. It's required for "
            "the RAG knowledge base's embeddings."
        )

    return GoogleGenerativeAIEmbeddings(
        model=settings.google_embedding_model,
        google_api_key=settings.google_api_key,
    )
