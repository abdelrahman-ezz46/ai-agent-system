"""
One adapter, many providers.

Ollama, Mistral, Google (compat endpoint), GitHub Models, Groq, Together, and
OpenAI itself all speak the *same* "OpenAI Chat Completions" wire format. So
this single file covers all of them — the only thing that changes is `base_url`
and the API key (both come from config.yaml).

That's the resume line: "supported N providers with one adapter using the
OpenAI-compatible standard."
"""

import json

from openai import OpenAI

from .base import AssistantReply, Provider, ToolCall


class OpenAICompatProvider(Provider):
    def __init__(self, model: str, base_url: str, api_key: str):
        self.model = model
        # Ollama doesn't check the key but the client library requires a non-empty
        # string, so we fall back to a placeholder.
        self.client = OpenAI(base_url=base_url, api_key=api_key or "not-needed")

    def chat(self, messages, tools, system) -> AssistantReply:
        wire_messages = self._to_openai_messages(messages, system)
        wire_tools = self._to_openai_tools(tools)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=wire_messages,
            tools=wire_tools or None,   # pass None (not []) when there are no tools
        )

        msg = response.choices[0].message
        reply = AssistantReply(text=msg.content or "")

        for call in (msg.tool_calls or []):
            # Arguments come back as a JSON *string* — parse to a dict. Small
            # local models sometimes emit slightly malformed JSON; degrade
            # gracefully instead of crashing the whole agent.
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_raw": call.function.arguments}
            reply.tool_calls.append(
                ToolCall(id=call.id, name=call.function.name, arguments=args)
            )

        return reply

    # ── translation: neutral -> OpenAI wire format ──────────────────────────
    def _to_openai_messages(self, messages, system):
        out = [{"role": "system", "content": system}]
        for m in messages:
            role = m["role"]
            if role == "tool":
                out.append({
                    "role": "tool",
                    "tool_call_id": m["tool_call_id"],
                    "content": m["content"],
                })
            elif role == "assistant" and m.get("tool_calls"):
                out.append({
                    "role": "assistant",
                    "content": m.get("content") or "",
                    "tool_calls": [{
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    } for tc in m["tool_calls"]],
                })
            else:
                out.append({"role": role, "content": m.get("content", "")})
        return out

    def _to_openai_tools(self, tools):
        return [{
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        } for t in tools]
