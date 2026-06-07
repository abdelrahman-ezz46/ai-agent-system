"""
The "universal plug" — one common interface every provider implements.

The agent loop talks ONLY to this interface. It never imports `anthropic` or
`openai` directly, so swapping Llama -> Claude is a one-line config change.

The shared language between the loop and any provider is:
    provider.chat(messages, tools, system) -> AssistantReply

where `messages` and `AssistantReply` use the neutral shapes defined below.
Each concrete adapter is responsible for translating to/from its own API.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """A request from the model to run one tool. Provider-neutral."""
    id: str            # unique id, used to match the result back to the call
    name: str          # which tool, e.g. "run_shell"
    arguments: dict    # the parsed arguments, e.g. {"command": "ls ~/Downloads"}


@dataclass
class AssistantReply:
    """What a provider hands back after one turn. Provider-neutral."""
    text: str = ""                          # any prose the model wrote
    tool_calls: list[ToolCall] = field(default_factory=list)  # tools it wants to run

    @property
    def wants_tools(self) -> bool:
        return len(self.tool_calls) > 0


# ── The neutral message format the loop uses ────────────────────────────────
# Conversation history is a list of plain dicts in one of these shapes:
#
#   {"role": "user", "content": "organize my downloads"}
#
#   {"role": "assistant", "content": "I'll list the folder first",
#    "tool_calls": [ToolCall(...), ...]}          # tool_calls optional
#
#   {"role": "tool", "tool_call_id": "...", "name": "run_shell",
#    "content": "<the tool's output>"}
#
# Each adapter below knows how to turn this into its provider's wire format.


class Provider(ABC):
    """Base class. Implement `chat` for each provider."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str,
    ) -> AssistantReply:
        """Send the conversation + available tools, get back one reply.

        `tools` is a neutral list of {name, description, parameters(JSON schema)}.
        """
        ...
