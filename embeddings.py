"""
Embeddings — the engine behind *semantic* memory recall (the RAG upgrade).

An embedding turns text into a vector (a list of numbers) that captures its
meaning. Two texts with similar meaning have vectors that point in similar
directions, which we measure with cosine similarity. That's how the agent can
recall "the user likes Python" when asked "what languages do they prefer?" —
different words, same meaning.

By default we use a LOCAL Ollama embedding model (nomic-embed-text) — free, no
API key, same OpenAI-compatible client we already use. If embeddings aren't
available (model not pulled, server down, disabled in config), everything
degrades gracefully to keyword search — the agent never breaks.
"""

from __future__ import annotations

import math

from openai import OpenAI


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two vectors, in [-1, 1]. Higher = more similar."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class Embedder:
    """Wraps any OpenAI-compatible /v1/embeddings endpoint (Ollama by default)."""

    def __init__(self, model: str, base_url: str, api_key: str = ""):
        self.model = model
        self.client = OpenAI(base_url=base_url, api_key=api_key or "not-needed")
        self._available: bool | None = None   # cached probe result
        # nomic-embed-text REQUIRES task prefixes to separate stored facts from
        # search queries — without them, unrelated sentences look falsely
        # similar and recall returns junk. Other models ignore this.
        self._nomic = "nomic" in model.lower()

    def embed(self, text: str, kind: str = "document") -> list[float]:
        """Embed text. `kind` is "document" (a stored fact) or "query" (a search)."""
        if self._nomic:
            prefix = "search_query: " if kind == "query" else "search_document: "
            text = prefix + text
        resp = self.client.embeddings.create(model=self.model, input=text)
        return resp.data[0].embedding

    def available(self) -> bool:
        """Probe once whether embeddings actually work, and cache the result.

        This is what makes the fallback safe: if the model isn't pulled or the
        server is down, we find out here and the Memory store uses keywords.
        """
        if self._available is None:
            try:
                self.embed("probe")
                self._available = True
            except Exception:
                self._available = False
        return self._available


def build_embedder(config: dict) -> Embedder | None:
    """Create an Embedder from config, or None to disable semantic recall."""
    model = config.get("embed_model")
    if not model:
        return None
    base_url = config.get("embed_base_url") or "http://localhost:11434/v1"
    api_key = config.get("embed_api_key") or config.get("api_key") or ""
    return Embedder(model=model, base_url=base_url, api_key=api_key)
