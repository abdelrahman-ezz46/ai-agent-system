"""
Claude adapter.

Claude's tool-use format differs slightly from the OpenAI one (it uses typed
content blocks instead of a separate `tool_calls` array), so it gets its own
small adapter. The payoff: rock-solid tool calling for demos.

Uses the official `anthropic` SDK and the manual agentic-loop shape — we make
one request per turn and let agent.py drive the loop.
"""

import anthropic

from .base import AssistantReply, Provider, ToolCall


class ClaudeProvider(Provider):
    def __init__(self, model: str, api_key: str):
        self.model = model
        # If api_key is blank, the SDK reads ANTHROPIC_API_KEY from the env.
        self.client = anthropic.Anthropic(api_key=api_key or None)

    def chat(self, messages, tools, system) -> AssistantReply:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            tools=self._to_claude_tools(tools),
            messages=self._to_claude_messages(messages),
        )

        reply = AssistantReply()
        for block in response.content:
            if block.type == "text":
                reply.text += block.text
            elif block.type == "tool_use":
                # block.input is already a parsed dict in the Anthropic SDK.
                reply.tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=block.input)
                )
        return reply

    # ── translation: neutral -> Anthropic wire format ───────────────────────
    def _to_claude_messages(self, messages):
        out = []
        for m in messages:
            role = m["role"]
            if role == "user":
                out.append({"role": "user", "content": m["content"]})

            elif role == "assistant":
                # Rebuild the assistant turn as text + tool_use blocks.
                blocks = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m.get("tool_calls", []):
                    blocks.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                out.append({"role": "assistant", "content": blocks})

            elif role == "tool":
                # Tool results live in a *user* message as tool_result blocks.
                # If the previous neutral message was also a tool result, merge
                # into the same user turn (Anthropic prefers one user message
                # carrying all results for a parallel tool call).
                result_block = {
                    "type": "tool_result",
                    "tool_use_id": m["tool_call_id"],
                    "content": m["content"],
                }
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                    out[-1]["content"].append(result_block)
                else:
                    out.append({"role": "user", "content": [result_block]})
        return out

    def _to_claude_tools(self, tools):
        return [{
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        } for t in tools]
