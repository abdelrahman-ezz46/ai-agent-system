"""Tool package: registry + the built-in tools."""

from memory import Memory
from safety import Sandbox
from .files import build_file_tools
from .memory_tools import build_memory_tools
from .registry import Registry, Tool
from .shell import SHELL_TOOL


def build_registry(sandbox: Sandbox, memory: Memory) -> Registry:
    """Assemble the agent's toolbox. Add new tools here as you build them.

    File tools are bound to the sandbox so their path checks are enforced.
    Memory tools are bound to the long-term store.
    """
    registry = Registry()
    registry.register(SHELL_TOOL)
    for tool in build_file_tools(sandbox):
        registry.register(tool)
    for tool in build_memory_tools(memory):
        registry.register(tool)
    return registry


__all__ = ["Registry", "Tool", "build_registry"]
