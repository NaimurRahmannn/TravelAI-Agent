from langchain.tools import tool

from app.retriever.knowledge_retriever import index_exists, search_knowledge_base


@tool
def search_travel_knowledge(query: str, k: int = 3) -> dict:
    """Search the travel knowledge base for background info that general
    trip-planning knowledge alone might not cover, e.g. general visa/entry
    guidance, packing tips, safety and health notes, or etiquette and
    culture pointers. Not for real-time data (use weather/budget/maps
    tools for that).
    """
    if not index_exists():
        return {
            "error": (
                "The knowledge base hasn't been built yet. Run "
                "`python -m app.retriever.build_index` after adding "
                "documents to the knowledge directory."
            )
        }

    matches = search_knowledge_base(query, k=k)

    if not matches:
        return {"query": query, "results": []}

    return {
        "query": query,
        "results": [
            {
                "text": match["text"],
                "source": match["metadata"].get("source"),
                "relevance": round(match["score"], 4),
            }
            for match in matches
        ],
    }