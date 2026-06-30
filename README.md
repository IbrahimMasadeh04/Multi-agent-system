# Multi-Agent Orchestrator

This project is a multi-agent assistant built with LangGraph, FastAPI, Streamlit, MCP, ChromaDB, and several LLM-backed workers. It routes user requests across internal document search, web search, SQL analysis, approval-gated database updates, and a file-generation subgraph that talks to an MCP server.

## What It Does

The system is organized around a LangGraph workflow that first classifies the user's request, then routes it to the right worker, and finally synthesizes a response.

Supported capabilities:

- Conversational chat over the API and Streamlit UI
- PDF upload and indexing into ChromaDB for internal RAG
- External web search through Tavily
- SQL-based analysis over the local Venom SQLite database
- Human approval flow for write operations such as insert, update, and delete
- File generation and template workflows through an MCP server

## High-Level Architecture

The main runtime entrypoint is the FastAPI app in [src/main.py](src/main.py), which exposes the API used by the Streamlit client in [src/features/UI/chat.py](src/features/UI/chat.py).

The LangGraph workflow in [src/features/agents/graph.py](src/features/agents/graph.py) wires together these nodes:

- `intent_analyzer` for intent and entity extraction
- `orchestrator` for routing decisions
- `planner` for multi-step requests
- `internal_search` for ChromaDB-based document retrieval
- `external_search` for Tavily-powered web search
- `db_analyst` for SQL generation and database analysis
- `sql_executor_node` for executing approved write operations
- `synthesizer` for final response generation
- `file_generator` as a nested subgraph for MCP-backed template and file workflows

The file-generation branch is implemented as a nested graph in [src/features/agents/file_generator_graph.py](src/features/agents/file_generator_graph.py) and calls MCP tools through [src/features/agents/mcp_client.py](src/features/agents/mcp_client.py).

## Repository Layout

- [src/main.py](src/main.py) - FastAPI application entrypoint
- [src/apis/routes.py](src/apis/routes.py) - API routes for chat, upload, and approval
- [src/features/agents/](src/features/agents) - LangGraph nodes, state, schemas, MCP client, and file-generation subgraph
- [src/features/ingestion/service.py](src/features/ingestion/service.py) - PDF ingestion and ChromaDB search
- [src/features/db_analyst/service.py](src/features/db_analyst/service.py) - SQL database helpers
- [src/features/UI/](src/features/UI) - Streamlit pages for chat and MCP inspection
- [src/helper/config.py](src/helper/config.py) - Environment configuration
- [src/helper/shared.py](src/helper/shared.py) - Shared LLM, embedding, and database helpers
- [README.md](README.md) - Project overview and setup

## Prerequisites

- Python 3.10 or newer
- Access to the configured OpenAI model and embeddings
- Tavily API key for external web search
- Google API key if the configured MCP or downstream workflows require it
- A running MCP server for template and file-generation operations
- A local SQLite database at the path configured in `VENOM_DB_PATH`

## Environment Variables

The app reads configuration from `.env` via [src/helper/config.py](src/helper/config.py). The current settings class expects these values:

- `LANGSMITH_PROJECT`
- `LANGSMITH_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_LLM`
- `OPENAI_LLM_TEMPERATURE`
- `OPENAI_EMBEDDING_MODEL`
- `GOOGLE_API_KEY`
- `TAVILY_API_KEY`
- `CHROMA_DB_PATH`
- `UPLOAD_DIR`
- `LANGCHAIN_TRACING_V2`
- `PROJECT_NAME`
- `VENOM_DB_PATH`
- `LANGSMITH_ENDPOINT`
- `LANGSMITH_TRACING`
- `CLIENT_URI`

Example:

```env
PROJECT_NAME=Multi-Agent API
OPENAI_API_KEY=...
OPENAI_LLM=gpt-4o-mini
OPENAI_LLM_TEMPERATURE=0
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
TAVILY_API_KEY=...
CHROMA_DB_PATH=./chroma_db
UPLOAD_DIR=./uploads
VENOM_DB_PATH=./VenomBackups/venom_backup_2026-04-22_14-26-36.db3
CLIENT_URI=http://127.0.0.1:8080/mcp
```

## Setup

1. Create and activate a virtual environment.
2. Install the package in editable mode.

```bash
pip install -e .
```

3. Install the development extras if you want tests and linting.

```bash
pip install -e .[dev]
```

4. Create a `.env` file in the project root and populate the required values.

## Run the App

Start the FastAPI backend:

```bash
uvicorn src.main:app --reload
```

Start the Streamlit UI in a second terminal:

```bash
streamlit run src/features/UI/chat.py
```

If you want the Streamlit navigation shell instead of the direct chat page, run:

```bash
streamlit run src/features/UI/streamlit_app.py
```

The file-generation workflows expect an MCP server at the URL defined by `CLIENT_URI`. The code currently points to `http://127.0.0.1:8080/mcp` for the file-generation subgraph.

## API Endpoints

The FastAPI app exposes these routes:

- `GET /` - basic welcome message
- `GET /health` - health check
- `POST /api/upload` - upload a PDF and index it into ChromaDB
- `POST /api/chat` - send a user message to the LangGraph workflow
- `POST /api/approve` - approve or reject a pending write query

### Chat Flow

1. The user sends a message to `POST /api/chat`.
2. The graph classifies the message and routes it to the right worker.
3. If the DB worker detects a write operation, the graph pauses and returns `status=interrupted` with the pending SQL.
4. The UI can call `POST /api/approve` with `approved=true` or `false` to resume or cancel execution.

## Main Workflows

### Internal Document Search

PDF files uploaded through the UI are processed in [src/features/ingestion/service.py](src/features/ingestion/service.py), chunked, embedded, and stored in ChromaDB. Queries against internal documents use similarity search over that vector store.

### Database Analysis

The DB analyst worker inspects the configured SQLite database, generates SQL, and submits it through the MCP tool layer. Read queries are summarized back to the user, while write queries require human approval before execution.

### External Search

The external worker uses Tavily to search the public web for current information or general knowledge tasks.

### File Generation

The file-generation subgraph supports template browsing, filling, QA, and orchestration. It loops through MCP tools until the workflow reaches a `done` state.

## Development Notes

- The graph definition lives in [src/features/agents/graph.py](src/features/agents/graph.py).
- State shape is defined in [src/features/agents/state.py](src/features/agents/state.py).
- Structured output schemas are defined in [src/features/agents/schemas.py](src/features/agents/schemas.py).
- The Streamlit chat UI can trigger document upload, pending approval, and normal chat responses.
- The repository includes a `Makefile` with test and lint targets for local development.

## Tests and Linting

Run unit tests:

```bash
make test
```

Run linting and formatting checks:

```bash
make lint
make format
```

## Notes

The original LangGraph starter text has been replaced with documentation for the actual multi-agent application in this repository.

