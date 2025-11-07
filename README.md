## Agno Streaming Chatbot

FastAPI + Agno + NiceGUI application for uploading PDFs and chatting with an agent that answers questions grounded in uploaded documents. Includes streaming responses (SSE), optional user memory storage (PostgreSQL), a NiceGUI frontend, and a full test suite.

### Features
- Upload a PDF and chat with an agent that cites context from the document
- Robust context handling: irrelevant questions no longer pollute memory
- “Thinking” section: brief rationale bullets before the answer
- Async-first backend with streaming via SSE
- Optional user memory persistence with PostgreSQL (async SQLAlchemy)
- Modern typing throughout (e.g., `list[str]`, `str | None`)

---

## Quickstart

### Requirements
- Python 3.13+ (project tested on 3.13)
- Node not required (NiceGUI runs on Python)
- Optional: PostgreSQL if you enable memories

### Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

### Environment
Create a `.env` in the project root (used by `pydantic-settings`):
```env
OPENAI_API_KEY=your_key_here
DATABASE_URL=postgresql+asyncpg://ai:ai@localhost:5432/ai  (for memories)
```

### Run backend (FastAPI)
```bash
source .venv/bin/activate
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Run UI (NiceGUI)
```bash
source .venv/bin/activate
python -m ui.nicegui_app
```
Open UI: `http://localhost:8080`

---

## Project Structure

- `backend/app/main.py` – FastAPI app, PDF upload endpoint, streaming chat endpoint
- `backend/app/agent.py` – Agno `Agent` wrapper with streaming and memory extraction
- `backend/app/pdfs.py` – PDF parsing via `pypdf`, metadata, storage to `pdf_text/`
- `backend/app/schemas.py` – Pydantic models (requests, chunks, metadata)
- `backend/app/db/memories.py` – Async SQL for `user_memories` table (optional)
- `backend/app/db/memory_utils.py` – Conservative memory extraction heuristics
- `ui/nicegui_app.py` – Simple NiceGUI client: upload + chat with streaming
- `tests/` – Unit and integration tests (httpx + pytest)

---

## Usage Flow
1) Upload a PDF via UI or API
2) Ask questions; the backend builds context from PDF text (+ recent memories)
3) The server emits a “thinking” event with 2–4 rationale bullets
4) Then the final answer streams token-by-token as SSE

---

## Testing

```bash
source .venv/bin/activate
pytest -v
```

What’s covered:
- Config and agent instantiation
- PDF parsing success and error cases
- End-to-end upload + stream workflow (with httpx ASGI transport)

---

## Cursor Configuration (IDE) – How this project was set up

This project was built with Cursor IDE to accelerate development with AI assistance and integrated documentation.

### MCP Servers (Docs wired into Cursor)
- `Agno` docs – agent patterns, streaming usage
- `FastAPI` docs – async endpoints, StreamingResponse, Pydantic v2
- `NiceGUI` docs – UI components and async handlers

These were added as MCP/Docs providers so inline lookups and code actions could reference the correct APIs without leaving the editor.

### Linters/Formatters
- `ruff` – primary linter (PEP8, static checks). Surfaced directly in-editor via gutter warnings and Problems panel
- `black` – auto-format on save across the repo
- `mypy` – optional static typing checks locally; helped ensure modern typing upgrades (e.g., `list[str]`, `str | None]`)

Cursor surfaced linter errors inline and in the Problems panel, enabling quick fixes and autofixes from suggestions.

### .cursorrules (project conventions)
We standardized rules (mirroring repo rules) to guide AI completions:
- Naming: functions/variables `snake_case`, classes `PascalCase`
- Style: Google-style docstrings; comments in full sentences
- Async: prefer async entrypoints and non-blocking operations

Purpose: keep AI-generated edits consistent with repo standards and reduce review time.

### Documentation Indexing & IDE features
- Project and dependency docs were indexed so definitions and examples were available inline
- Inline type hints and signature help ensured consistent modern typing

### What actually helped us move faster and write simpler code
- Cursor.ai helped us alot to make it streamline and saved our time
- AI-assisted refactoring made large typing and streaming changes safe and quick
- Combining `ruff` + `black` kept code review trivial (style diffs disappeared)
- httpx ASGI transport in tests simplified integration testing without a live server

---

## Notes & Gotchas
- Ensure `OPENAI_API_KEY` is set before running the backend
- UI expects backend on `http://localhost:8001`; adjust `BACKEND_URL` in `ui/nicegui_app.py` if needed
- If using DB memories, confirm PostgreSQL is reachable and the table exists

---

## License
MIT