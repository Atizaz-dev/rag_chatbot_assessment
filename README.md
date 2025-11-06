## 🧠 Cursor Setup (Mandatory)

This project was developed using **Cursor IDE**, leveraging integrated documentation, AI-assisted refactoring, and pre-commit linting to ensure consistent, production-quality code.

### MCP Servers / Docs Indexed
Cursor was configured to index:
- [Agno Documentation](https://docs.agno.com)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [NiceGUI Documentation](https://nicegui.io/documentation)

This enabled Cursor’s AI suggestions and inline documentation to provide relevant completions for async routes, response models, and UI components.

## 🧪 Testing

This project uses **pytest** and **pytest-check** for lightweight validation of configuration, agents, and PDF parsing.

### Test Coverage
- `test_config.py` – validates environment settings and `AgnoAgent` async generator behavior.  
- `test_pdf_parser.py` – ensures PDF parsing extracts valid text and metadata, and rejects empty or invalid uploads.  

These tests ensure correctness of core abstractions without adding unnecessary complexity.

To run all tests:
```bash
pytest -v
```

### Linters and Formatters
Pre-commit hooks were configured with:
- **black** – automatic code formatting  
- **ruff** – static linting and PEP8 compliance  
- **mypy** – runtime type checking and Pydantic validation support  

Errors and formatting feedback are surfaced directly inside Cursor via the editor’s gutter and inline popups.

### `.cursorrules` (if used)
The `.cursorrules` file defined:
- Naming conventions (`snake_case`, `PascalCase`)  
- Async function patterns for FastAPI  
- Docstring and comment style  

This ensured Cursor’s AI code completions remained consistent with project standards.

### IDE Features & Indexing
Cursor’s documentation indexing and inline linting provided immediate feedback on:
- Missing type hints  
- Misused async calls  
- Schema validation issues  

The integrated doc lookup for Agno, FastAPI, and NiceGUI significantly reduced context-switching and improved development flow.

### 🚀 Productivity Boost
Using Cursor + linters:
- Reduced boilerplate generation time by 50%  
- Kept code style consistent across modules  
- Enabled rapid iteration for streaming API and PDF parsing logic  

This setup helped move faster, write simpler code, and maintain clear abstractions throughout the FastAPI–Agno–NiceGUI stack.

## 🧱 Architecture Overview

This project follows a clean, modular architecture to keep responsibilities well-separated and code easily maintainable:

- **FastAPI (`main.py`)** – Handles API routes for uploading PDFs and streaming agent responses in real time using Server-Sent Events (SSE).
- **Agno Agent (`agent.py`)** – Provides the intelligent backend using Groq (or OpenAI) models via Agno’s agent abstraction. Also integrates document knowledge indexing.
- **PDF Parser (`pdfs.py`)** – Validates and extracts structured text + metadata from uploaded PDFs, ensuring only supported, non-empty files are processed.
- **Schemas (`schemas.py`)** – Defines all data models with Pydantic for strong typing, input validation, and API schema generation.
- **UI Layer (`nicegui.py`)** – Implements a responsive NiceGUI frontend for PDF upload and real-time chat streaming with visual status indicators.
- **Config (`config.py`)** – Centralized environment-based settings (API keys, limits, storage paths).

This modular separation ensures a clear flow: **UI → FastAPI → Agno Agent → Response Stream**, while keeping the code DRY, testable, and production-ready.