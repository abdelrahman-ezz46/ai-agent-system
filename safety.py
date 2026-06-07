"""
The safety layer — three cheap features that make this project sound mature:

  1. Dangerous-action detection: flag commands that can destroy data.
  2. Path sandbox: the agent may only operate inside allowed folders.
  3. Confirmation gate: a human approves anything dangerous before it runs.

This is the "human-in-the-loop" story that interviewers love hearing.
"""

import os
import re

# Patterns that should trigger a confirmation prompt. Not exhaustive — it's a
# safety net, not a security boundary. The sandbox below is the real fence.
_DANGEROUS_PATTERNS = [
    r"\brm\b", r"\brmdir\b", r"\bmv\b", r"\bdd\b", r"\bmkfs",
    r"\bshutdown\b", r"\breboot\b", r"\bkill(all)?\b",
    r"\bgit\s+push\b", r"\bgit\s+reset\s+--hard\b",
    r">\s*/?\w",          # output redirection that overwrites a file
    r"\bchmod\b", r"\bchown\b", r"\bsudo\b",
    r"\bcurl\b.*\|\s*(ba)?sh",   # curl | sh
]
_DANGEROUS_RE = re.compile("|".join(_DANGEROUS_PATTERNS))


def looks_dangerous(command: str) -> bool:
    """True if a shell command matches a destructive pattern."""
    return bool(_DANGEROUS_RE.search(command))


# Binaries we can trust to only READ. Used by dry-run mode: in preview, a shell
# command runs only if it's provably read-only, otherwise it's blocked — this
# closes the hole where a model creates files via `touch`/`tee`/`cat >` that the
# destructive-pattern check above wouldn't flag.
_READONLY_BINS = {
    "ls", "cat", "head", "tail", "grep", "egrep", "fgrep", "find", "wc",
    "pwd", "echo", "file", "stat", "du", "df", "tree", "which", "date",
    "basename", "dirname", "realpath", "sort", "uniq", "cut", "nl", "column",
}
# Any of these in a command means we can't reason about it simply → not safe.
_SHELL_METACHARS = (">", "<", "|", "&", ";", "$(", "`", "\n")


def is_readonly_command(command: str) -> bool:
    """Conservatively true only for a single read-only command.

    Rejects redirection, pipes, chaining, and command substitution outright,
    then requires the program itself to be on the read-only allowlist.
    """
    cmd = (command or "").strip()
    if not cmd or any(meta in cmd for meta in _SHELL_METACHARS):
        return False
    program = os.path.basename(cmd.split()[0])
    return program in _READONLY_BINS


class Sandbox:
    """Restricts file/shell operations to a set of allowed directories."""

    def __init__(self, allowed_paths: list[str]):
        # Expand "~" and make absolute so comparisons are reliable.
        self.allowed = [os.path.realpath(os.path.expanduser(p)) for p in allowed_paths]

    def is_allowed(self, path: str) -> bool:
        target = os.path.realpath(os.path.expanduser(path))
        return any(
            target == root or target.startswith(root + os.sep)
            for root in self.allowed
        )

    def describe(self) -> str:
        return ", ".join(self.allowed)
