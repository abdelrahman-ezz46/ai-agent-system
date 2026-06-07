"""
The most powerful tool in the box: run a shell command.

With just this one tool the agent can already explore the filesystem, inspect
files, set up projects, run scripts, and more. It's marked `dangerous=True` so
every call goes through the confirmation gate (see agent.py / safety.py).
"""

import subprocess

from safety import looks_dangerous
from .registry import Tool

# Cap output so a chatty command (e.g. `find /`) can't blow up the context.
_MAX_OUTPUT_CHARS = 4000


def run_shell(command: str) -> str:
    """Execute `command` in a shell and return combined stdout+stderr."""
    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 60 seconds."

    output = (completed.stdout or "") + (completed.stderr or "")
    output = output.strip() or "(command produced no output)"

    if len(output) > _MAX_OUTPUT_CHARS:
        output = output[:_MAX_OUTPUT_CHARS] + "\n... (output truncated)"

    return f"[exit code {completed.returncode}]\n{output}"


# The Tool definition the registry will expose to the model.
SHELL_TOOL = Tool(
    name="run_shell",
    description=(
        "Run a shell command on the user's computer and return its output. "
        "Use this to inspect files and folders, run scripts, or perform tasks. "
        "Prefer read-only commands (ls, cat, grep) before making changes."
    ),
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The exact shell command to execute.",
            },
        },
        "required": ["command"],
    },
    func=run_shell,
    dangerous=True,
    # Only confirm when the command looks destructive — read-only commands
    # (ls, cat, grep) run without interruption.
    confirm_when=lambda args: looks_dangerous(args.get("command", "")),
)
