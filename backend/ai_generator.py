import anthropic
from typing import List, Optional

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to search and course outline tools.

Tool Usage:
- **search_course_content**: Use for questions about specific course content or detailed educational materials
- **get_course_outline**: Use when the user asks for a course outline, lesson list, course structure, table of contents, or what topics/lessons a course covers
- **Up to 2 sequential tool calls per query** — use a second tool call only when the first result is insufficient or when a different tool would complement the answer
- Synthesize tool results into accurate, fact-based responses
- If a tool yields no results, state this clearly without offering alternatives

When presenting course outlines:
- Include the course title and instructor
- Include the course link as a clickable markdown link
- List all lessons as a numbered list with lesson numbers and titles
- Present the complete lesson list from the tool result — do not summarize or truncate

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Use the appropriate tool first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results" or "based on the tool results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        
        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
        
        # Get response from Claude and handle up to MAX_TOOL_ROUNDS of tool calls
        MAX_TOOL_ROUNDS = 2

        response = self.client.messages.create(**api_params)

        for _ in range(MAX_TOOL_ROUNDS):
            if response.stop_reason != "tool_use" or not tool_manager:
                return self._extract_text(response)

            # Append assistant's tool-use response
            api_params["messages"].append({"role": "assistant", "content": response.content})

            # Execute all tool calls and collect results
            tool_results = []
            tool_failed = False
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result = tool_manager.execute_tool(block.name, **block.input)
                    except Exception as e:
                        result = f"Tool execution error: {str(e)}"
                        tool_failed = True
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # Append tool results
            if tool_results:
                api_params["messages"].append({"role": "user", "content": tool_results})

            # Make follow-up API call
            response = self.client.messages.create(**api_params)

            # If a tool call failed, return after this follow-up (don't continue looping)
            if tool_failed:
                return self._extract_text(response)

        # Loop exhausted (hit MAX_TOOL_ROUNDS) — return whatever text is in the last response
        return self._extract_text(response)

    def _extract_text(self, response) -> str:
        """Extract the first text block from a response."""
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""