"""Tests for FastAPI API endpoints.

Covers /api/query, /api/courses, /api/session/{session_id}, and /.
Uses the test_app and client fixtures from conftest.py, which provide a
FastAPI app wired to a mock_rag so no real ChromaDB or Anthropic calls occur.
"""


class TestQueryEndpoint:
    """POST /api/query — request/response handling."""

    def test_returns_200_and_correct_body(self, client, mock_rag):
        mock_rag.query.return_value = ("The answer", ["Source 1"])
        mock_rag.session_manager.create_session.return_value = "session_auto"

        resp = client.post("/api/query", json={"query": "What is MCP?"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"] == "The answer"
        assert body["sources"] == ["Source 1"]
        assert body["session_id"] == "session_auto"

    def test_uses_provided_session_id(self, client, mock_rag):
        mock_rag.query.return_value = ("Answer", [])

        resp = client.post(
            "/api/query",
            json={"query": "Follow-up", "session_id": "existing_session"},
        )

        assert resp.status_code == 200
        assert resp.json()["session_id"] == "existing_session"
        # create_session must NOT have been called when a session_id was supplied
        mock_rag.session_manager.create_session.assert_not_called()
        mock_rag.query.assert_called_once_with("Follow-up", "existing_session")

    def test_auto_creates_session_when_none_provided(self, client, mock_rag):
        mock_rag.session_manager.create_session.return_value = "new_session"
        mock_rag.query.return_value = ("Answer", [])

        client.post("/api/query", json={"query": "Hello"})

        mock_rag.session_manager.create_session.assert_called_once()

    def test_auto_session_id_appears_in_response(self, client, mock_rag):
        mock_rag.session_manager.create_session.return_value = "generated_session"
        mock_rag.query.return_value = ("Answer", [])

        body = client.post("/api/query", json={"query": "Hello"}).json()

        assert body["session_id"] == "generated_session"

    def test_returns_500_on_rag_error(self, client, mock_rag):
        mock_rag.session_manager.create_session.return_value = "s1"
        mock_rag.query.side_effect = RuntimeError("RAG system failure")

        resp = client.post("/api/query", json={"query": "Failing query"})

        assert resp.status_code == 500
        assert "RAG system failure" in resp.json()["detail"]

    def test_response_has_required_fields(self, client, mock_rag):
        mock_rag.query.return_value = ("Answer", ["src1", "src2"])
        mock_rag.session_manager.create_session.return_value = "s1"

        body = client.post("/api/query", json={"query": "test"}).json()

        assert {"answer", "sources", "session_id"} <= body.keys()
        assert isinstance(body["sources"], list)

    def test_missing_query_field_returns_422(self, client):
        resp = client.post("/api/query", json={})
        assert resp.status_code == 422

    def test_empty_sources_list_is_valid(self, client, mock_rag):
        mock_rag.query.return_value = ("Direct answer", [])
        mock_rag.session_manager.create_session.return_value = "s1"

        resp = client.post("/api/query", json={"query": "simple"})

        assert resp.status_code == 200
        assert resp.json()["sources"] == []

    def test_multiple_sources_returned_intact(self, client, mock_rag):
        sources = ["Course A - Lesson 1", "Course B - Lesson 3"]
        mock_rag.query.return_value = ("Answer with many sources", sources)
        mock_rag.session_manager.create_session.return_value = "s1"

        body = client.post("/api/query", json={"query": "broad question"}).json()

        assert body["sources"] == sources


class TestCoursesEndpoint:
    """GET /api/courses — course analytics."""

    def test_returns_200_and_course_list(self, client, mock_rag):
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 3,
            "course_titles": ["Course A", "Course B", "Course C"],
        }

        resp = client.get("/api/courses")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_courses"] == 3
        assert body["course_titles"] == ["Course A", "Course B", "Course C"]

    def test_response_has_required_fields(self, client, mock_rag):
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }

        body = client.get("/api/courses").json()

        assert "total_courses" in body
        assert "course_titles" in body
        assert isinstance(body["course_titles"], list)

    def test_returns_500_on_error(self, client, mock_rag):
        mock_rag.get_course_analytics.side_effect = RuntimeError("DB failure")

        resp = client.get("/api/courses")

        assert resp.status_code == 500
        assert "DB failure" in resp.json()["detail"]

    def test_empty_catalog(self, client, mock_rag):
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }

        resp = client.get("/api/courses")

        assert resp.status_code == 200
        assert resp.json()["total_courses"] == 0
        assert resp.json()["course_titles"] == []

    def test_course_count_matches_titles_length(self, client, mock_rag):
        titles = ["Intro to AI", "Advanced NLP", "MCP Patterns"]
        mock_rag.get_course_analytics.return_value = {
            "total_courses": len(titles),
            "course_titles": titles,
        }

        body = client.get("/api/courses").json()

        assert body["total_courses"] == len(body["course_titles"])


class TestSessionEndpoint:
    """DELETE /api/session/{session_id} — session lifecycle."""

    def test_clear_session_returns_success(self, client, mock_rag):
        resp = client.delete("/api/session/session_42")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert "session_42" in body["message"]

    def test_clear_session_calls_rag_with_correct_id(self, client, mock_rag):
        client.delete("/api/session/my_session")

        mock_rag.session_manager.clear_session.assert_called_once_with("my_session")

    def test_clear_session_returns_500_on_error(self, client, mock_rag):
        mock_rag.session_manager.clear_session.side_effect = RuntimeError("Session not found")

        resp = client.delete("/api/session/bad_session")

        assert resp.status_code == 500
        assert "Session not found" in resp.json()["detail"]


class TestRootEndpoint:
    """GET / — basic availability check."""

    def test_returns_200(self, client):
        assert client.get("/").status_code == 200
