"""
File tools: read_file, write_file, list_dir.

Unlike run_shell (which we can only loosely guard), these take an explicit
`path` argument — so we can *enforce* the sandbox precisely. Each tool is built
by a factory that closes over the Sandbox, so the path check is baked in and
can't be bypassed.

If the model targets a path outside the allowed folders, the tool returns a
clear "Blocked" message. The model reads that and adapts — no crash.
"""

from __future__ import annotations

import os

from safety import Sandbox
from .registry import Tool

# Cap how much a single read dumps into the model's context.
_MAX_READ_CHARS = 4000


def build_file_tools(sandbox: Sandbox) -> list[Tool]:
    """Create the file tools, each bound to this sandbox."""

    # ── read_file (safe, read-only) ─────────────────────────────────────────
    def read_file(path: str) -> str:
        if not sandbox.is_allowed(path):
            return _blocked(path, sandbox)
        full = os.path.expanduser(path)
        if not os.path.isfile(full):
            return f"Error: no such file '{path}'."
        try:
            with open(full, "r", errors="replace") as f:
                content = f.read()
        except Exception as e:
            return f"Error reading '{path}': {e}"
        if len(content) > _MAX_READ_CHARS:
            content = content[:_MAX_READ_CHARS] + "\n... (file truncated)"
        return content or "(empty file)"

    # ── list_dir (safe, read-only) ──────────────────────────────────────────
    def list_dir(path: str = ".") -> str:
        if not sandbox.is_allowed(path):
            return _blocked(path, sandbox)
        full = os.path.expanduser(path)
        if not os.path.isdir(full):
            return f"Error: no such directory '{path}'."
        entries = sorted(os.listdir(full))
        if not entries:
            return "(empty directory)"
        # Mark directories with a trailing slash so the model can tell them apart.
        lines = [
            name + ("/" if os.path.isdir(os.path.join(full, name)) else "")
            for name in entries
        ]
        return "\n".join(lines)

    # ── write_file (DANGEROUS — overwrites; always confirmed) ───────────────
    def write_file(path: str, content: str) -> str:
        if not sandbox.is_allowed(path):
            return _blocked(path, sandbox)
        full = os.path.expanduser(path)
        try:
            parent = os.path.dirname(full)
            if parent:
                os.makedirs(parent, exist_ok=True)  # parent is inside sandbox too
            with open(full, "w") as f:
                f.write(content)
        except Exception as e:
            return f"Error writing '{path}': {e}"
        return f"Wrote {len(content)} characters to {path}."

    return [
        Tool(
            name="read_file",
            description="Read and return the contents of a text file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file."}
                },
                "required": ["path"],
            },
            func=read_file,
        ),
        Tool(
            name="list_dir",
            description="List the files and folders in a directory.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (defaults to current dir).",
                    }
                },
                "required": [],
            },
            func=list_dir,
        ),
        Tool(
            name="write_file",
            description=(
                "Create or overwrite a text file with the given content. "
                "This replaces the whole file."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to write to."},
                    "content": {"type": "string", "description": "Full file contents."},
                },
                "required": ["path", "content"],
            },
            func=write_file,
            dangerous=True,   # always routed through the confirmation gate
        ),
    ]


def _blocked(path: str, sandbox: Sandbox) -> str:
    return (
        f"Blocked: '{path}' is outside the allowed folders "
        f"({sandbox.describe()}). Ask the user to add it to allowed_paths if needed."
    )
