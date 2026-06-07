"""
Tools shipped by the `text-stats` skill.

A skill's tools.py just needs a `get_tools(context)` function returning a list of
Tool objects. `context` carries shared services from the host — here we use the
sandbox so the tool can't read files outside the allowed folders.
"""

import os
from collections import Counter

# Skills live next to the core code, so this import works when loaded.
from tools.registry import Tool


def get_tools(context):
    sandbox = context.get("sandbox")

    def count_text_stats(path: str) -> str:
        # Respect the same sandbox the built-in file tools use.
        if sandbox is not None and not sandbox.is_allowed(path):
            return f"Blocked: '{path}' is outside the allowed folders."
        full = os.path.expanduser(path)
        if not os.path.isfile(full):
            return f"Error: no such file '{path}'."
        try:
            with open(full, "r", errors="replace") as f:
                text = f.read()
        except Exception as e:
            return f"Error reading '{path}': {e}"

        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        words = text.split()
        common = Counter(w.strip(".,!?;:\"'()").lower() for w in words if w.strip())
        top = ", ".join(f"{w}({n})" for w, n in common.most_common(5)) or "(none)"
        return (
            f"lines: {lines}\nwords: {len(words)}\ncharacters: {len(text)}\n"
            f"top words: {top}"
        )

    return [
        Tool(
            name="count_text_stats",
            description="Count lines, words, characters, and top words in a text file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the text file."}
                },
                "required": ["path"],
            },
            func=count_text_stats,
        )
    ]
