"""Tests for AIGenerator — tool calling, message structure, BUG 4 detection."""

from unittest.mock import MagicMock, patch, call
from ai_generator import AIGenerator


# --------------- helpers ---------------

def _text_block(text):
    """Create a mock TextBlock."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _tool_use_block(tool_id, name, input_dict):
    """Create a mock ToolUseBlock."""
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = input_dict
    return block


def _message(content_blocks, stop_reason="end_turn"):
    """Create a mock Message response."""
    msg = MagicMock()
    msg.content = content_blocks
    msg.stop_reason = stop_reason
    return msg


def _make_generator():
    """Create an AIGenerator with a mocked Anthropic client."""
    with patch("ai_generator.anthropic.Anthropic") as MockClient:
        gen = AIGenerator(api_key="fake-key", model="claude-test")
        # gen.client is already the mock instance created by Anthropic()
        return gen, gen.client


# =============== Tests ===============


class TestAIGeneratorDirectResponse:

    def test_direct_text_response(self):
        gen, client = _make_generator()
        client.messages.create.return_value = _message(
            [_text_block("Hello world")], stop_reason="end_turn"
        )

        result = gen.generate_response("Hi")
        assert result == "Hello world"

    def test_tools_passed_but_not_used(self):
        gen, client = _make_generator()
        client.messages.create.return_value = _message(
            [_text_block("I can answer directly")], stop_reason="end_turn"
        )

        tool_mgr = MagicMock()
        tools = [{"name": "search_course_content", "input_schema": {}}]
        result = gen.generate_response("What is 2+2?", tools=tools, tool_manager=tool_mgr)

        assert result == "I can answer directly"
        tool_mgr.execute_tool.assert_not_called()


class TestAIGeneratorToolExecution:

    def test_tool_use_triggers_execution(self):
        gen, client = _make_generator()

        tool_block = _tool_use_block("tu_1", "search_course_content", {"query": "MCP"})
        first_response = _message([tool_block], stop_reason="tool_use")
        second_response = _message([_text_block("Here are the results")], stop_reason="end_turn")
        client.messages.create.side_effect = [first_response, second_response]

        tool_mgr = MagicMock()
        tool_mgr.execute_tool.return_value = "Found: MCP content"
        tools = [{"name": "search_course_content", "input_schema": {}}]

        result = gen.generate_response("Tell me about MCP", tools=tools, tool_manager=tool_mgr)

        tool_mgr.execute_tool.assert_called_once_with("search_course_content", query="MCP")
        assert result == "Here are the results"

    def test_tool_execution_message_structure(self):
        gen, client = _make_generator()

        tool_block = _tool_use_block("tu_1", "search_course_content", {"query": "test"})
        first_response = _message([_text_block("Let me search"), tool_block], stop_reason="tool_use")
        second_response = _message([_text_block("Final answer")], stop_reason="end_turn")
        client.messages.create.side_effect = [first_response, second_response]

        tool_mgr = MagicMock()
        tool_mgr.execute_tool.return_value = "tool output"
        tools = [{"name": "search_course_content", "input_schema": {}}]

        gen.generate_response("q", tools=tools, tool_manager=tool_mgr)

        # Second call's messages should have 3 entries:
        # [0] user message, [1] assistant content blocks, [2] user tool_results
        second_call_kwargs = client.messages.create.call_args_list[1]
        messages = second_call_kwargs.kwargs.get("messages") or second_call_kwargs[1].get("messages")
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"

    def test_tool_result_format(self):
        gen, client = _make_generator()

        tool_block = _tool_use_block("tu_42", "search_course_content", {"query": "x"})
        first_response = _message([tool_block], stop_reason="tool_use")
        second_response = _message([_text_block("done")], stop_reason="end_turn")
        client.messages.create.side_effect = [first_response, second_response]

        tool_mgr = MagicMock()
        tool_mgr.execute_tool.return_value = "result text"
        tools = [{"name": "search_course_content", "input_schema": {}}]

        gen.generate_response("q", tools=tools, tool_manager=tool_mgr)

        second_call_kwargs = client.messages.create.call_args_list[1]
        messages = second_call_kwargs.kwargs.get("messages") or second_call_kwargs[1].get("messages")
        tool_result_msg = messages[2]
        tool_results = tool_result_msg["content"]

        assert len(tool_results) == 1
        tr = tool_results[0]
        assert tr["type"] == "tool_result"
        assert tr["tool_use_id"] == "tu_42"
        assert tr["content"] == "result text"

    def test_followup_call_includes_tools(self):
        """Verify the follow-up API call after tool execution includes 'tools'
        so the API can validate tool_result messages in the history."""
        gen, client = _make_generator()

        tool_block = _tool_use_block("tu_1", "search_course_content", {"query": "q"})
        first_response = _message([tool_block], stop_reason="tool_use")
        second_response = _message([_text_block("answer")], stop_reason="end_turn")
        client.messages.create.side_effect = [first_response, second_response]

        tool_mgr = MagicMock()
        tool_mgr.execute_tool.return_value = "data"
        tools = [{"name": "search_course_content", "input_schema": {}}]

        gen.generate_response("q", tools=tools, tool_manager=tool_mgr)

        second_call_kwargs = client.messages.create.call_args_list[1]
        followup_params = second_call_kwargs.kwargs if second_call_kwargs.kwargs else second_call_kwargs[1]

        assert "tools" in followup_params, (
            "Follow-up API call must include 'tools' when tool_result messages are in history"
        )
        assert followup_params["tools"] == tools


class TestAIGeneratorConversationHistory:

    def test_conversation_history_in_system(self):
        gen, client = _make_generator()
        client.messages.create.return_value = _message(
            [_text_block("resp")], stop_reason="end_turn"
        )

        gen.generate_response("q", conversation_history="User: hi\nAssistant: hello")

        call_kwargs = client.messages.create.call_args
        system = call_kwargs.kwargs.get("system") or call_kwargs[1].get("system")
        assert "Previous conversation:" in system
        assert "User: hi" in system

    def test_no_history_uses_base_system(self):
        gen, client = _make_generator()
        client.messages.create.return_value = _message(
            [_text_block("resp")], stop_reason="end_turn"
        )

        gen.generate_response("q")

        call_kwargs = client.messages.create.call_args
        system = call_kwargs.kwargs.get("system") or call_kwargs[1].get("system")
        assert system == AIGenerator.SYSTEM_PROMPT
        assert "Previous conversation:" not in system


class TestAIGeneratorEdgeCases:

    def test_tool_use_without_tool_manager(self):
        """When stop_reason is tool_use but no tool_manager provided,
        code falls through to response.content[0].text."""
        gen, client = _make_generator()

        text_block = _text_block("I would search but no manager")
        tool_block = _tool_use_block("tu_1", "search_course_content", {"query": "q"})
        # When tool_manager is None, code goes to response.content[0].text
        response = _message([text_block, tool_block], stop_reason="tool_use")
        client.messages.create.return_value = response

        # With text block first, this should work
        result = gen.generate_response("q")
        assert result == "I would search but no manager"

    def test_multiple_tool_calls(self):
        gen, client = _make_generator()

        tool1 = _tool_use_block("tu_1", "search_course_content", {"query": "a"})
        tool2 = _tool_use_block("tu_2", "get_course_outline", {"course_name": "MCP"})
        first_response = _message([tool1, tool2], stop_reason="tool_use")
        second_response = _message([_text_block("combined answer")], stop_reason="end_turn")
        client.messages.create.side_effect = [first_response, second_response]

        tool_mgr = MagicMock()
        tool_mgr.execute_tool.side_effect = ["result A", "result B"]
        tools = [{"name": "search_course_content"}, {"name": "get_course_outline"}]

        result = gen.generate_response("q", tools=tools, tool_manager=tool_mgr)

        assert tool_mgr.execute_tool.call_count == 2
        assert result == "combined answer"
