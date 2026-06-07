# Skills — teach the agent new tricks

A **skill** is a drop-in folder that gives the agent a reusable playbook for a
kind of task, and can ship its own Python tools. You add capabilities **without
touching the core code** — just create a folder here.

## Anatomy

```
skills/
  my-skill/
    SKILL.md      # required — what the skill is + how to do the task
    tools.py      # optional — Python tools the skill provides
```

### `SKILL.md` (required)

Markdown with a small frontmatter block:

```markdown
---
name: my-skill
description: One line — shown to the agent so it knows when to use this skill.
---

# Instructions

Step-by-step guidance the agent follows once it loads this skill.
```

- **`name`** — how the agent refers to the skill (used by `use_skill`).
- **`description`** — always visible to the agent; keep it a single, specific line.
- **body** — the full instructions, loaded **on demand** when the agent calls
  `use_skill("my-skill")`. This "progressive disclosure" keeps the base prompt
  small while supporting many skills.

### `tools.py` (optional)

Expose a `get_tools(context)` that returns a list of `Tool` objects:

```python
from tools.registry import Tool

def get_tools(context):
    sandbox = context.get("sandbox")   # shared services from the host

    def my_action(path: str) -> str:
        if sandbox and not sandbox.is_allowed(path):
            return "Blocked: outside the sandbox."
        ...                              # do the work
        return "result string"

    return [Tool(
        name="my_action",
        description="What it does (the agent reads this to decide to call it).",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "..."}},
            "required": ["path"],
        },
        func=my_action,
    )]
```

Tools returned here are registered automatically at startup and go through the
same safety gate as built-in tools (mark one `dangerous=True` to require
confirmation).

## How the agent uses skills

1. At startup, every skill's `name: description` is injected into the system
   prompt under **"Available skills."**
2. When a task matches, the agent calls **`use_skill(name)`** to load the full
   instructions, then follows them (and uses any tools the skill registered).

## Examples in this folder

- **`text-stats/`** — instructions **plus** a custom `count_text_stats` tool.
- **`git-helper/`** — instructions only (drives the built-in `run_shell`).

## Try it

```bash
python main.py "how many words are in notes.txt?"     # uses text-stats
python main.py "check the git status and show me the diff"   # uses git-helper
```
