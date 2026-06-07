"""
Skills — user-addable capabilities, loaded from the `skills/` folder.

A *skill* teaches the agent how to do a specific kind of task, and can ship its
own Python tools. This is how a user extends the agent WITHOUT touching the core
code: just drop a folder in `skills/`.

    skills/
      my-skill/
        SKILL.md      # required: frontmatter (name, description) + instructions
        tools.py      # optional: def get_tools(context) -> list[Tool]

Progressive disclosure (the same idea real agent "skills" use): the agent always
sees each skill's one-line *description*, but only loads the full instructions
when it decides the skill is relevant — by calling the `use_skill` tool. That
keeps the base prompt small while making many skills available on demand.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field

from tools.registry import Registry, Tool


@dataclass
class Skill:
    name: str
    description: str
    instructions: str
    tools: list[Tool] = field(default_factory=list)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a `--- key: value --- body` markdown file into (meta, body)."""
    meta: dict = {}
    body = text.strip()
    if body.startswith("---"):
        end = body.find("\n---", 3)
        if end != -1:
            block = body[3:end].strip()
            body = body[end + 4:].strip()
            for line in block.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip()] = value.strip()
    return meta, body


def _load_skill_tools(tools_path: str, context: dict) -> list[Tool]:
    """Import a skill's tools.py and call its get_tools(context)."""
    spec = importlib.util.spec_from_file_location(
        f"skill_tools_{os.path.basename(os.path.dirname(tools_path))}", tools_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "get_tools"):
        return list(module.get_tools(context) or [])
    return []


def load_skills(skills_dir: str, context: dict | None = None) -> list[Skill]:
    """Discover and load every skill under `skills_dir`."""
    context = context or {}
    skills: list[Skill] = []
    skills_dir = os.path.expanduser(skills_dir)
    if not os.path.isdir(skills_dir):
        return skills

    for name in sorted(os.listdir(skills_dir)):
        folder = os.path.join(skills_dir, name)
        skill_md = os.path.join(folder, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        try:
            with open(skill_md) as f:
                meta, body = _parse_frontmatter(f.read())
            skill = Skill(
                name=meta.get("name", name),
                description=meta.get("description", "(no description)"),
                instructions=body,
            )
            tools_py = os.path.join(folder, "tools.py")
            if os.path.isfile(tools_py):
                skill.tools = _load_skill_tools(tools_py, context)
            skills.append(skill)
        except Exception as e:
            # A broken skill shouldn't take down the whole agent — skip it.
            print(f"⚠ skipping skill '{name}': {e}")
    return skills


def skills_overview(skills: list[Skill]) -> str:
    """The one-line-per-skill summary injected into the system prompt."""
    if not skills:
        return ""
    return "\n".join(f"- {s.name}: {s.description}" for s in skills)


def build_use_skill_tool(skills: list[Skill]) -> Tool:
    """A tool that returns a skill's full instructions on demand."""
    by_name = {s.name: s for s in skills}

    def use_skill(name: str) -> str:
        skill = by_name.get(name)
        if skill is None:
            available = ", ".join(by_name) or "(none)"
            return f"No skill named '{name}'. Available skills: {available}"
        return f"# Skill: {skill.name}\n\n{skill.instructions}"

    return Tool(
        name="use_skill",
        description=(
            "Load the full step-by-step instructions for a named skill BEFORE "
            "doing a task it covers. Check the 'Available skills' list first."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The skill's name."}
            },
            "required": ["name"],
        },
        func=use_skill,
    )


def register_skills(registry: Registry, skills: list[Skill]) -> str:
    """Register every skill's tools + the use_skill tool. Returns the overview."""
    if not skills:
        return ""
    for skill in skills:
        for tool in skill.tools:
            registry.register(tool)
    registry.register(build_use_skill_tool(skills))
    return skills_overview(skills)
