"""Tests for RAGSystem query orchestration — BUG 3 detection, source tracking."""

from unittest.mock import MagicMock, patch, PropertyMock
from vector_store import SearchResults
from search_tools import CourseSearchTool, ToolManager


# --------------- helpers ---------------

def _make_config():
    """Create a mock config with required attributes."""
    config = MagicMock()
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.CHROMA_PATH = "/tmp/test_chroma"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.MAX_RESULTS = 5
    config.ANTHROPIC_API_KEY = "fake-key"
    config.ANTHROPIC_MODEL = "claude-test"
    config.MAX_HISTORY = 2
    return config


def _results(docs, metas, dists=None, error=None):
    if dists is None:
        dists = [0.1] * len(docs)
    return SearchResults(documents=docs, metadata=metas, distances=dists, error=error)


# =============== Tests ===============


class TestRAGSystemQuery:

    @patch("rag_system.SessionManager")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    def test_query_returns_response_and_sources(self, MockDP, MockVS, MockAI, MockSM):
        from rag_system import RAGSystem

        MockAI.return_value.generate_response.return_value = "The answer is 42"
        config = _make_config()
        rag = RAGSystem(config)
        # Manually set sources so get_last_sources returns them
        rag.tool_manager = MagicMock()
        rag.tool_manager.get_last_sources.return_value = ["Source A"]
        rag.tool_manager.get_tool_definitions.return_value = []

        response, sources = rag.query("What is 42?")

        assert response == "The answer is 42"
        assert sources == ["Source A"]

    @patch("rag_system.SessionManager")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    def test_query_passes_raw_query(self, MockDP, MockVS, MockAI, MockSM):
        """Verify query() passes the user's query directly without redundant wrapping,
        since the system prompt already provides context."""
        from rag_system import RAGSystem

        mock_ai = MockAI.return_value
        mock_ai.generate_response.return_value = "resp"
        config = _make_config()
        rag = RAGSystem(config)
        rag.tool_manager = MagicMock()
        rag.tool_manager.get_last_sources.return_value = []
        rag.tool_manager.get_tool_definitions.return_value = []

        rag.query("What is MCP?")

        call_kwargs = mock_ai.generate_response.call_args
        actual_query = call_kwargs.kwargs.get("query") or call_kwargs[0][0]

        assert actual_query == "What is MCP?", (
            "Query should be passed directly without wrapping prefix"
        )

    @patch("rag_system.SessionManager")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    def test_query_passes_tools_and_manager(self, MockDP, MockVS, MockAI, MockSM):
        from rag_system import RAGSystem

        mock_ai = MockAI.return_value
        mock_ai.generate_response.return_value = "resp"
        config = _make_config()
        rag = RAGSystem(config)

        rag.query("q")

        call_kwargs = mock_ai.generate_response.call_args
        # Should have tools and tool_manager kwargs
        assert "tools" in call_kwargs.kwargs
        assert "tool_manager" in call_kwargs.kwargs
        assert call_kwargs.kwargs["tool_manager"] is rag.tool_manager

    @patch("rag_system.SessionManager")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    def test_sources_collected_and_reset(self, MockDP, MockVS, MockAI, MockSM):
        from rag_system import RAGSystem

        MockAI.return_value.generate_response.return_value = "resp"
        config = _make_config()
        rag = RAGSystem(config)
        rag.tool_manager = MagicMock()
        rag.tool_manager.get_last_sources.return_value = ["S1"]
        rag.tool_manager.get_tool_definitions.return_value = []

        rag.query("q")

        rag.tool_manager.get_last_sources.assert_called_once()
        rag.tool_manager.reset_sources.assert_called_once()

    @patch("rag_system.SessionManager")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    def test_session_history_updated(self, MockDP, MockVS, MockAI, MockSM):
        from rag_system import RAGSystem

        MockAI.return_value.generate_response.return_value = "answer"
        config = _make_config()
        rag = RAGSystem(config)
        rag.tool_manager = MagicMock()
        rag.tool_manager.get_last_sources.return_value = []
        rag.tool_manager.get_tool_definitions.return_value = []

        rag.query("hello?", session_id="s1")

        rag.session_manager.add_exchange.assert_called_once()
        args = rag.session_manager.add_exchange.call_args[0]
        assert args[0] == "s1"
        assert args[1] == "hello?"
        assert args[2] == "answer"

    @patch("rag_system.SessionManager")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    def test_query_without_session(self, MockDP, MockVS, MockAI, MockSM):
        from rag_system import RAGSystem

        MockAI.return_value.generate_response.return_value = "resp"
        config = _make_config()
        rag = RAGSystem(config)
        rag.tool_manager = MagicMock()
        rag.tool_manager.get_last_sources.return_value = []
        rag.tool_manager.get_tool_definitions.return_value = []

        rag.query("q")  # No session_id

        rag.session_manager.add_exchange.assert_not_called()
        rag.session_manager.get_conversation_history.assert_not_called()

    @patch("rag_system.SessionManager")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    def test_conversation_history_passed(self, MockDP, MockVS, MockAI, MockSM):
        from rag_system import RAGSystem

        mock_ai = MockAI.return_value
        mock_ai.generate_response.return_value = "resp"
        mock_sm = MockSM.return_value
        mock_sm.get_conversation_history.return_value = "User: hi\nAssistant: hello"
        config = _make_config()
        rag = RAGSystem(config)

        rag.query("follow-up?", session_id="s1")

        call_kwargs = mock_ai.generate_response.call_args
        assert call_kwargs.kwargs["conversation_history"] == "User: hi\nAssistant: hello"

    @patch("rag_system.SessionManager")
    @patch("rag_system.AIGenerator")
    @patch("rag_system.VectorStore")
    @patch("rag_system.DocumentProcessor")
    def test_end_to_end_tool_flow(self, MockDP, MockVS, MockAI, MockSM):
        """Full mock flow: query -> generate_response -> tool_use -> tool exec -> final response.
        Uses a real ToolManager + CourseSearchTool with mock VectorStore."""
        from rag_system import RAGSystem

        config = _make_config()

        # We need to construct a RAGSystem but intercept the AI generator
        # to simulate the tool use flow
        mock_ai = MockAI.return_value
        mock_vs = MockVS.return_value

        rag = RAGSystem(config)

        # Set up the mock vector store to return results when searched
        mock_vs.search.return_value = _results(
            ["MCP is a protocol"],
            [{"course_title": "MCP Course", "lesson_number": 1}],
        )
        mock_vs.get_lesson_link.return_value = "https://example.com/l1"

        # Simulate: first call returns tool_use, handler calls tool, second call returns text
        def simulate_generate(query, conversation_history=None, tools=None, tool_manager=None):
            # Simulate the tool being called (as the real generate_response would)
            if tool_manager:
                result = tool_manager.execute_tool(
                    "search_course_content", query="MCP"
                )
                assert "MCP is a protocol" in result
            return "MCP is a Model Context Protocol"

        mock_ai.generate_response.side_effect = simulate_generate

        response, sources = rag.query("What is MCP?")

        assert response == "MCP is a Model Context Protocol"
        assert len(sources) > 0
        assert "https://example.com/l1" in sources[0]
