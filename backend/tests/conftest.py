"""Shared fixtures and test infrastructure for the RAG system test suite."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional


# ── Pydantic models mirroring app.py ─────────────────────────────────────────
# Redefined here to avoid importing app.py directly, which mounts static files
# from ../frontend — a directory that does not exist in the test environment.

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    session_id: str

class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_rag():
    """Pre-configured MagicMock that mimics RAGSystem's public interface.

    Tests can override individual return values or side_effects before making
    requests through the client fixture.
    """
    rag = MagicMock()
    rag.query.return_value = ("Test answer", ["Source A"])
    rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Course A", "Course B"],
    }
    rag.session_manager.create_session.return_value = "session_1"
    rag.session_manager.clear_session.return_value = None
    return rag


@pytest.fixture
def test_app(mock_rag):
    """FastAPI app with endpoints that mirror app.py, wired to mock_rag.

    Static file mounting is intentionally omitted so tests run without a
    built frontend.  The mock_rag captured here is the same instance that
    pytest injects into test functions that also request the mock_rag fixture,
    allowing per-test configuration of return values before requests are made.
    """
    app = FastAPI(title="Test RAG API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root():
        return {"status": "ok"}

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag.session_manager.create_session()
            answer, sources = mock_rag.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/session/{session_id}")
    async def clear_session(session_id: str):
        try:
            mock_rag.session_manager.clear_session(session_id)
            return {"status": "success", "message": f"Session {session_id} cleared"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def client(test_app):
    """Synchronous TestClient wrapping the test app."""
    with TestClient(test_app) as c:
        yield c
