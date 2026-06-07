"""
The tool registry.

A Tool bundles four things:
  - name & description    -> what the model sees when deciding to call it
  - parameters            -> a JSON Schema describing the arguments
  - func                  -> the Python function that actually does the work
  - dangerous             -> whether to route it through the confirmation gate

The Registry collects tools, hands their schemas to the provider, and runs the
right function when the model asks for one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict        # JSON Schema (object with "properties", "required")
    func: Callable          # func(**arguments) -> str
    dangerous: bool = False
    # Optional per-call check: given the arguments, return True if THIS specific
    # call needs confirmation. Lets run_shell confirm only on destructive
    # commands while still auto-running `ls`. If None, fall back to `dangerous`.
    confirm_when: Callable[[dict], bool] | None = None

    def is_dangerous_call(self, arguments: dict) -> bool:
        """Should this particular invocation be confirmed by a human?"""
        if self.confirm_when is not None:
            return self.confirm_when(arguments)
        return self.dangerous


class Registry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict]:
        """Neutral schema list the provider turns into its own tool format."""
        return [{
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        } for t in self._tools.values()]

    def run(self, name: str, arguments: dict) -> str:
        tool = self.get(name)
        if tool is None:
            return f"Error: no such tool '{name}'."
        try:
            return tool.func(**arguments)
        except TypeError as e:
            # Usually the model passed wrong/missing arguments — tell it so it
            # can correct itself on the next turn.
            return f"Error calling {name}: {e}"
        except Exception as e:
            return f"Error while running {name}: {e}"
