# TravelAI Agent

An AI-powered travel planning assistant. You chat with it in natural
language ("I want to go to Tokyo for 5 days with a $2000 budget"), and it
extracts your trip preferences, asks clarifying questions for anything
missing, then builds a day-by-day itinerary and can answer follow-up
questions using a set of live travel tools (weather, budget/currency,
maps, destination info, and a travel knowledge base).

## Architecture

```
app/
├── main.py               FastAPI app entrypoint
├── core/                 Settings (pydantic-settings) and logging
├── api/                  HTTP routes (/chat, /health)
├── chains/               LangChain chains: trip extraction, itinerary
│                         generation, tool-augmented chat
├── prompts/              Prompt templates for the chains above
├── schemas/              Pydantic request/response and domain models
├── services/             ChatService (orchestration) and
│                         ClarificationService (asks for missing trip info)
├── tools/                LangChain @tool-decorated functions the LLM can
│                         call: destination info, budget, currency,
│                         weather, maps, and knowledge base search
├── memory/               Persistence-facing stores (conversation history,
│                         trip preferences, itineraries) — backed by the
│                         database
├── database/             SQLAlchemy engine/session setup
├── models/                SQLAlchemy ORM models
├── retriever/             Knowledge base document loading, chunking,
│                         index building, and querying (RAG)
└── vectorstore/          Lightweight JSON-backed vector store + embeddings
```

A single `/chat` request flows like this:

1. Extract/update trip preferences (destination, dates, budget, travelers,
   duration) from the message via `trip_extraction_chain`.
2. If required fields are still missing, ask the next clarifying question.
3. Otherwise, if no itinerary exists yet for this conversation, generate
   one via `itinerary_chain`.
4. Otherwise, answer the user's follow-up question via `travel_chain`,
   which can call tools (weather, maps, budget, knowledge base, etc.) in a
   loop before producing a final response.

Conversation history, trip preferences, and itineraries all persist to a
database, so nothing is lost on restart.

## Setup

**Requirements:** Python 3.11+

```bash
git clone https://github.com/NaimurRahmannn/TravelAI-Agent.git
cd TravelAI-Agent
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.examples .env
```

Then fill in `.env`:

| Variable | Required | Purpose |
|---|---|---|
| `groq_api_key` | Yes | Powers the chat LLM (Groq/Llama) |
| `groq_model` | No | Defaults to `llama-3.3-70b-versatile` |
| `geoapify_api_key` | For map tools | Geocoding, routing, nearby places |
| `amadeus_api_key` / `amadeus_api_secret` | Optional | Live flight/hotel pricing in budget estimates |
| `aviationstack_api_key` | Optional | Live flight data in budget estimates |
| `database_url` | No | Defaults to a local SQLite file (`sqlite:///./travel_ai.db`) |
| `google_api_key` | For the knowledge base tool | Embeddings for RAG search (see below) |

Run the API:

```bash
uvicorn app.main:app --reload
```

On startup, the required database tables are created automatically if
they don't exist yet (SQLite by default — no separate setup needed). Then:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I want to visit Tokyo for 5 days with a $2000 budget, 2 travelers"}'

curl http://localhost:8000/health
```

## Database persistence

Conversation history, trip preferences, and generated itineraries are
stored via SQLAlchemy (SQLite by default — point `database_url` at
Postgres or another SQLAlchemy-supported database for production use).
Each `app/memory/*.py` store keeps the same interface `ChatService`
expects (`get_history`, `get_trip`/`update_trip`,
`get_itinerary`/`save_itinerary`/`delete_itinerary`); only the storage
backend changed, so nothing above the store layer needed to change.

## Knowledge base (RAG)

`app/tools/rag.py` exposes a `search_travel_knowledge` tool the agent can
call for general travel knowledge that isn't live data — visa/entry
basics, packing tips, safety and health notes, and cultural etiquette.
Sample documents live in `data/knowledge/`.

To (re)build the index after adding or editing documents in
`data/knowledge/`:

```bash
python -m app.retriever.build_index
```

This chunks each `.md`/`.txt` file, embeds the chunks with Google's
embedding model (`google_api_key` required), and saves the index to
`app/vectorstore/index.json`. The vector store itself is a small
dependency-free JSON file with pure-Python cosine similarity search — no
FAISS/Chroma installation required. Add more `.md`/`.txt` files to
`data/knowledge/` and re-run the command above to grow the knowledge base.

## Running tests

```bash
pip install pytest
pytest
```

Tests that exercise live third-party APIs (maps) are mocked; the database
tests use a temporary SQLite file so they never touch `travel_ai.db`.

## Known gaps / possible next steps

This project is still a work in progress. As of this README:

- **`app/agent/`** is empty — the current orchestration in `ChatService`
  is hand-written sequential chain calls rather than a LangGraph agent
  graph, despite `langgraph` being a dependency.
- **`app/tools/places.py`** and **`app/tools/visa.py`** are empty stubs —
  planned tools (a dedicated places/POI tool and a visa-requirement
  lookup tool) that haven't been implemented yet.
- **`frontend/`** is empty — this is currently a backend-only API with no
  UI.
