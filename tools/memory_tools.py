"""
Memory tools: `remember` and `recall`.

These let the *model* curate its own long-term memory. Giving the agent control
over what to save is the "agentic memory" pattern — the model decides what's
worth keeping, instead of us blindly logging everything.

Neither tool is dangerous: they only touch the agent's own notes file, never
the user's data, so they run without a confirmation prompt.
"""

from __future__ import annotations

from memory import Memory
from .registry import Tool


def build_memory_tools(memory: Memory) -> list[Tool]:
    def remember(note: str) -> str:
        return memory.add(note)

    def recall(query: str) -> str:
        hits = memory.search(query)
        if not hits:
            return "No matching memories."
        return "\n".join(f"- {h}" for h in hits)

    return [
        Tool(
            name="remember",
            description=(
                "Save a durable fact to long-term memory so FUTURE sessions "
                "benefit. Use it for the user's preferences, details about their "
                "system or projects, or a lesson worth keeping. One concise "
                "sentence per call. Don't save one-off task details, and don't "
                "save meta-notes about the act of remembering itself."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "note": {
                        "type": "string",
                        "description": "The fact to remember, as one sentence.",
                    }
                },
                "required": ["note"],
            },
            func=remember,
        ),
        Tool(
            name="recall",
            description="Search long-term memory for facts matching a keyword.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword(s) to search memories for.",
                    }
                },
                "required": ["query"],
            },
            func=recall,
        ),
    ]
