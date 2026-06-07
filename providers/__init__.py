"""
The provider factory: turn a config dict into the right Provider object.

This is the single place that knows about concrete providers. Add a new one by
adding a branch here — the rest of the codebase stays untouched.
"""

import os

from .base import AssistantReply, Provider, ToolCall

# Friendly aliases -> their OpenAI-compatible base URLs. If the user names one
# of these as `provider`, we use OpenAICompatProvider and fill in the URL.
OPENAI_COMPAT_BASE_URLS = {
    "mistral": "https://api.mistral.ai/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "github": "https://models.inference.ai.azure.com",
    "groq": "https://api.groq.com/openai/v1",
    "together": "https://api.together.xyz/v1",
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434/v1",
}


def build_provider(config: dict) -> Provider:
    name = config.get("provider", "ollama").lower()
    model = config["model"]
    # Key precedence: config.yaml -> AGENT_API_KEY env var -> "".
    api_key = config.get("api_key") or os.environ.get("AGENT_API_KEY", "")

    if name == "claude":
        from .claude import ClaudeProvider
        return ClaudeProvider(model=model, api_key=api_key)

    # Everything else is OpenAI-compatible.
    from .openai_compat import OpenAICompatProvider
    base_url = config.get("base_url") or OPENAI_COMPAT_BASE_URLS.get(name)
    if not base_url:
        raise ValueError(
            f"Unknown provider '{name}'. Use 'claude', one of "
            f"{list(OPENAI_COMPAT_BASE_URLS)}, or set base_url in config.yaml."
        )
    return OpenAICompatProvider(model=model, base_url=base_url, api_key=api_key)


__all__ = ["Provider", "AssistantReply", "ToolCall", "build_provider"]
