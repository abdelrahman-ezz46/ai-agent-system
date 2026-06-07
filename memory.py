"""
Long-term memory — the "gets better with each use" feature.

Two-tier memory design:
  - SHORT-TERM: the conversation `messages` list in the Agent (resets each run).
  - LONG-TERM: this store — a small JSON file of curated facts that SURVIVES
    across runs. The agent writes to it via the `remember` tool, and we inject
    relevant facts into the system prompt at the start of every session.

We deliberately store *distilled facts*, not raw transcripts. A pile of old
tool output is noise; "User prefers Python; projects live in ~/code" is signal.

M4 (semantic recall): each fact can carry an embedding vector. Search and prompt
injection then rank facts by *meaning* (cosine similarity), not exact words. If
no embedder is available, everything falls back to keyword search.
"""

from __future__ import annotations

import json
import os
import time

from embeddings import Embedder, cosine

# Similarity floor for the `recall` tool — below this, a "match" is probably
# junk. Calibrated empirically for nomic-embed-text with task prefixes:
#   real queries (incl. terse ones like "city location")  ~0.51 - 0.74
#   clearly-unrelated queries                             ~0.36 - 0.44
# 0.48 sits in the gap. Known limit: a query that shares phrasing with a stored
# fact ("user's favorite pizza?" vs "user's favorite language") can score ~0.56
# and slip through — embedding similarity can't fully separate those.
_RECALL_THRESHOLD = 0.48


class Memory:
    def __init__(self, path: str, embedder: Embedder | None = None):
        self.path = os.path.expanduser(path)
        self.embedder = embedder
        self.items = self._load()
        self._backfill_embeddings()   # migrate any facts saved before M4

    # ── persistence ─────────────────────────────────────────────────────────
    def _load(self) -> list[dict]:
        if not os.path.isfile(self.path):
            return []
        try:
            with open(self.path) as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            # A corrupt memory file shouldn't crash the agent — start fresh.
            return []

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.items, f, indent=2)

    # ── embeddings helpers ──────────────────────────────────────────────────
    def _embeddings_on(self) -> bool:
        return self.embedder is not None and self.embedder.available()

    def _safe_embed(self, text: str, kind: str = "document") -> list[float] | None:
        try:
            return self.embedder.embed(text, kind=kind)
        except Exception:
            return None

    def _backfill_embeddings(self):
        """Give an embedding to any older fact that lacks one (one-time migration)."""
        if not self._embeddings_on():
            return
        changed = False
        for item in self.items:
            if not item.get("embedding"):
                vec = self._safe_embed(item["text"])
                if vec is not None:
                    item["embedding"] = vec
                    changed = True
        if changed:
            self._save()

    def _rank_by_similarity(self, query: str) -> list[tuple[float, str]]:
        """Return (score, text) for every embedded fact, best first."""
        qv = self._safe_embed(query, kind="query")   # asymmetric: query vs documents
        if qv is None:
            return []
        scored = [
            (cosine(qv, item["embedding"]), item["text"])
            for item in self.items if item.get("embedding")
        ]
        scored.sort(reverse=True, key=lambda pair: pair[0])
        return scored

    # ── operations the tools call ───────────────────────────────────────────
    def add(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return "Nothing to remember."
        if any(item["text"].lower() == text.lower() for item in self.items):
            return "Already in memory — not duplicating."
        item = {"text": text, "saved_on": time.strftime("%Y-%m-%d")}
        if self._embeddings_on():
            item["embedding"] = self._safe_embed(text)  # may be None on failure
        self.items.append(item)
        self._save()
        return f"Remembered: {text}"

    def search(self, query: str, k: int = 5) -> list[str]:
        """Semantic search (by meaning) with a keyword fallback."""
        query = (query or "").strip()
        if not query:
            return []
        if self._embeddings_on():
            ranked = self._rank_by_similarity(query)
            hits = [text for score, text in ranked if score >= _RECALL_THRESHOLD][:k]
            if hits:
                return hits
            # Nothing semantically close — fall through to keyword as a backstop.
        q = query.lower()
        return [item["text"] for item in self.items if q in item["text"].lower()][:k]

    # ── used to seed the system prompt each session ─────────────────────────
    def context_for(self, goal: str, k: int = 8) -> str:
        """The facts to inject into the prompt for THIS goal.

        Small store → just show everything. Larger store with embeddings →
        retrieve the top-k most relevant to the goal (this is the RAG step).
        """
        if not self.items:
            return ""
        if self._embeddings_on() and goal and len(self.items) > k:
            ranked = self._rank_by_similarity(goal)
            if ranked:
                top = [text for _score, text in ranked[:k]]
                return "\n".join(f"- {t}" for t in top)
        return self.format_for_prompt(limit=k)

    def format_for_prompt(self, limit: int = 25) -> str:
        if not self.items:
            return ""
        recent = self.items[-limit:]
        return "\n".join(f"- {item['text']}" for item in recent)

    def count(self) -> int:
        return len(self.items)

    def mode(self) -> str:
        """For display: are we doing semantic or keyword recall?"""
        return "semantic" if self._embeddings_on() else "keyword"
