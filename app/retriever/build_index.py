"""Builds (or rebuilds) the RAG vector index from `data/knowledge/`.

Run as a script whenever knowledge documents are added or changed:

    python -m app.retriever.build_index
"""
from app.core.config import settings
from app.retriever.document_loader import chunk_text, load_documents
from app.vectorstore.embeddings import get_embeddings
from app.vectorstore.store import SimpleVectorStore


def build_index() -> int:
    """Rebuild the vector index. Returns the number of chunks indexed."""
    documents = load_documents(settings.knowledge_dir)

    if not documents:
        print(
            f"No .md/.txt files found in '{settings.knowledge_dir}'. "
            "Nothing to index."
        )
        return 0

    texts: list[str] = []
    metadatas: list[dict] = []

    for document in documents:
        for chunk in chunk_text(
            document.text,
            chunk_size=settings.rag_chunk_size,
            overlap=settings.rag_chunk_overlap,
        ):
            texts.append(chunk)
            metadatas.append({"source": document.source})

    store = SimpleVectorStore(
        persist_path=settings.vectorstore_path,
        embeddings=get_embeddings(),
    )
    store.reset()
    store.add_documents(texts, metadatas)
    store.save()

    print(
        f"Indexed {len(texts)} chunks from {len(documents)} document(s) "
        f"into '{settings.vectorstore_path}'."
    )
    return len(texts)


if __name__ == "__main__":
    build_index()
