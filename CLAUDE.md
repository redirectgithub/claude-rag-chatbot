
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Always use `uv` to run commands and manage dependencies—never use `pip` directly.**

```bash
# Install dependencies
uv sync

# Add a new dependency
uv add <package-name>

# Run a Python file
uv run python <file.py>

# Run the application (from project root)
./run.sh

# Or manually
cd backend && uv run uvicorn app:app --reload --port 8000

# Access points
# Web UI: http://localhost:8000
# API docs: http://localhost:8000/docs
```

## Environment Setup

Requires `.env` file in project root with:
```
ANTHROPIC_API_KEY=your-key-here
```

## Data Directories

- `docs/` - Course text files (`.txt` only, see Document Format below)
- `chroma_db/` - ChromaDB persistent storage (auto-created on first run)

## Architecture

This is a **tool-based RAG system** where Claude decides when and how to search course materials.

### Query Flow

```
Frontend (JS) → FastAPI → RAGSystem → AIGenerator → Claude API
                                          ↓
                              Claude returns tool_use
                                          ↓
                              ToolManager → CourseSearchTool → VectorStore → ChromaDB
                                          ↓
                              Results sent back to Claude for final response
```

### Backend Components (`backend/`)

| File | Purpose |
|------|---------|
| `app.py` | FastAPI server with `/api/query` and `/api/courses` endpoints |
| `rag_system.py` | Main orchestrator - coordinates all components |
| `ai_generator.py` | Claude API client with tool execution loop |
| `vector_store.py` | ChromaDB wrapper with two collections: `course_catalog` (metadata) and `course_content` (chunks) |
| `document_processor.py` | Parses course files, extracts metadata, chunks text (800 chars, 100 overlap) |
| `search_tools.py` | Abstract `Tool` base class, `CourseSearchTool`, and `ToolManager` |
| `session_manager.py` | Conversation history (max 2 exchanges) |
| `models.py` | Pydantic models: `Course`, `Lesson`, `CourseChunk` |
| `config.py` | Configuration from environment variables |

### Frontend (`frontend/`)

Vanilla HTML/CSS/JS with `marked.js` for markdown rendering. Sends POST to `/api/query` with query and session_id.

### Tool System

Claude is given a `search_course_content` tool with parameters:
- `query` (required): What to search for
- `course_name` (optional): Filters by course (semantic matching)
- `lesson_number` (optional): Filters by lesson

The AI decides autonomously whether to use the tool based on the question type.

### Document Format

Course files in `docs/` should follow:
```
Course Title: [title]
Course Link: [url]
Course Instructor: [name]

Lesson 0: [title]
Lesson Link: [url]
[content]

Lesson 1: [title]
[content]
```

### Key Configuration (in `config.py`)

- Model: `claude-sonnet-4-20250514`
- Embeddings: `all-MiniLM-L6-v2`
- Chunk size: 800 chars with 100 char overlap
- Max search results: 5
- Temperature: 0 (deterministic)
