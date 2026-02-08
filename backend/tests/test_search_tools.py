"""Tests for CourseSearchTool, CourseOutlineTool, and ToolManager."""

from unittest.mock import MagicMock
from vector_store import SearchResults
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager


# --------------- helpers ---------------

def _make_store():
    """Return a MagicMock that quacks like VectorStore."""
    return MagicMock()


def _results(docs, metas, dists=None, error=None):
    """Shortcut to build a SearchResults dataclass."""
    if dists is None:
        dists = [0.1] * len(docs)
    return SearchResults(documents=docs, metadata=metas, distances=dists, error=error)


# =============== CourseSearchTool ===============


class TestCourseSearchToolExecute:

    def test_execute_successful_search(self):
        store = _make_store()
        store.search.return_value = _results(
            ["chunk A"], [{"course_title": "Intro", "lesson_number": 1}]
        )
        store.get_lesson_link.return_value = None
        store.get_course_link.return_value = None

        tool = CourseSearchTool(store)
        result = tool.execute(query="hello")

        store.search.assert_called_once_with(query="hello", course_name=None, lesson_number=None)
        assert "chunk A" in result

    def test_execute_empty_results(self):
        store = _make_store()
        store.search.return_value = _results([], [])

        tool = CourseSearchTool(store)
        result = tool.execute(query="nothing")

        assert result == "No relevant content found."

    def test_execute_empty_results_with_filters(self):
        store = _make_store()
        store.search.return_value = _results([], [])

        tool = CourseSearchTool(store)
        result = tool.execute(query="q", course_name="MCP", lesson_number=3)

        assert "in course 'MCP'" in result
        assert "in lesson 3" in result

    def test_execute_error_from_store(self):
        store = _make_store()
        store.search.return_value = _results([], [], error="Search error: timeout")

        tool = CourseSearchTool(store)
        result = tool.execute(query="q")

        assert result == "Search error: timeout"

    def test_execute_with_course_name_filter(self):
        store = _make_store()
        store.search.return_value = _results([], [])

        tool = CourseSearchTool(store)
        tool.execute(query="q", course_name="MCP")

        store.search.assert_called_once_with(query="q", course_name="MCP", lesson_number=None)

    def test_execute_with_lesson_number_filter(self):
        store = _make_store()
        store.search.return_value = _results([], [])

        tool = CourseSearchTool(store)
        tool.execute(query="q", lesson_number=5)

        store.search.assert_called_once_with(query="q", course_name=None, lesson_number=5)


class TestCourseSearchToolFormatResults:

    def test_format_results_with_lesson_links(self):
        store = _make_store()
        store.get_lesson_link.return_value = "https://example.com/lesson1"

        tool = CourseSearchTool(store)
        results = _results(
            ["content here"],
            [{"course_title": "Intro", "lesson_number": 1}],
        )
        tool._format_results(results)

        assert len(tool.last_sources) == 1
        assert "https://example.com/lesson1" in tool.last_sources[0]
        assert "[Intro - Lesson 1]" in tool.last_sources[0]

    def test_format_results_falls_back_to_course_link(self):
        store = _make_store()
        store.get_lesson_link.return_value = None
        store.get_course_link.return_value = "https://example.com/course"

        tool = CourseSearchTool(store)
        results = _results(
            ["content"],
            [{"course_title": "Intro", "lesson_number": 2}],
        )
        tool._format_results(results)

        assert "https://example.com/course" in tool.last_sources[0]

    def test_format_results_no_links(self):
        store = _make_store()
        store.get_lesson_link.return_value = None
        store.get_course_link.return_value = None

        tool = CourseSearchTool(store)
        results = _results(
            ["content"],
            [{"course_title": "Intro", "lesson_number": 1}],
        )
        tool._format_results(results)

        assert tool.last_sources == ["Intro - Lesson 1"]

    def test_format_results_no_lesson_number(self):
        store = _make_store()
        store.get_course_link.return_value = None

        tool = CourseSearchTool(store)
        results = _results(
            ["content"],
            [{"course_title": "Intro", "lesson_number": None}],
        )
        output = tool._format_results(results)

        # Header should be "[Intro]" without " - Lesson None"
        assert "[Intro]" in output
        assert "Lesson None" not in output


# =============== CourseOutlineTool ===============


class TestCourseOutlineTool:

    def test_outline_tool_execute_success(self):
        store = _make_store()
        store.get_course_outline.return_value = {
            "title": "MCP Course",
            "instructor": "Alice",
            "course_link": "https://example.com/mcp",
            "lesson_count": 2,
            "lessons": [
                {"lesson_number": 1, "lesson_title": "Intro"},
                {"lesson_number": 2, "lesson_title": "Advanced"},
            ],
        }

        tool = CourseOutlineTool(store)
        result = tool.execute(course_name="MCP")

        assert "MCP Course" in result
        assert "Alice" in result
        assert "Lesson 1: Intro" in result
        assert "Lesson 2: Advanced" in result
        assert "Total Lessons: 2" in result

    def test_outline_tool_execute_no_match(self):
        store = _make_store()
        store.get_course_outline.return_value = None

        tool = CourseOutlineTool(store)
        result = tool.execute(course_name="nonexistent")

        assert result == "No course found matching 'nonexistent'."


# =============== ToolManager ===============


class TestToolManager:

    def test_tool_manager_dispatch(self):
        store = _make_store()
        store.search.return_value = _results(
            ["found it"],
            [{"course_title": "C", "lesson_number": 1}],
        )
        store.get_lesson_link.return_value = None
        store.get_course_link.return_value = None

        mgr = ToolManager()
        mgr.register_tool(CourseSearchTool(store))

        result = mgr.execute_tool("search_course_content", query="test")
        assert "found it" in result

    def test_tool_manager_unknown_tool(self):
        mgr = ToolManager()
        result = mgr.execute_tool("doesnt_exist", foo="bar")
        assert result == "Tool 'doesnt_exist' not found"

    def test_tool_manager_source_tracking(self):
        store = _make_store()
        store.search.return_value = _results(
            ["doc"],
            [{"course_title": "C", "lesson_number": 1}],
        )
        store.get_lesson_link.return_value = None
        store.get_course_link.return_value = None

        mgr = ToolManager()
        mgr.register_tool(CourseSearchTool(store))
        mgr.execute_tool("search_course_content", query="q")

        sources = mgr.get_last_sources()
        assert len(sources) == 1

        mgr.reset_sources()
        assert mgr.get_last_sources() == []

    def test_tool_manager_get_definitions(self):
        store = _make_store()
        mgr = ToolManager()
        mgr.register_tool(CourseSearchTool(store))
        mgr.register_tool(CourseOutlineTool(store))

        defs = mgr.get_tool_definitions()
        assert len(defs) == 2
        names = {d["name"] for d in defs}
        assert names == {"search_course_content", "get_course_outline"}
