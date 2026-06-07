"""
The "nice TUI" — a thin wrapper over `rich`.

Every method here is just pretty printing. Keeping it in one file means the
agent loop stays readable (it calls ui.show_action(...) instead of fiddling
with colors inline), and you can later swap this for a full `textual` app
without touching the loop.
"""

from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

console = Console()


def banner(provider: str, model: str, sandbox: str,
           memory_count: int = 0, memory_mode: str = "keyword",
           mode: str = "interactive", skill_count: int = 0):
    mem = (f"remembering {memory_count} fact(s) · {memory_mode} recall"
           if memory_count else f"no memories yet · {memory_mode} recall")
    console.print(Panel.fit(
        Text.assemble(
            ("🤖  Terminal Agent\n", "bold cyan"),
            (f"provider: {provider}   model: {model}\n", "dim"),
            (f"sandbox:  {sandbox}\n", "dim"),
            (f"memory:   🧠 {mem}\n", "dim"),
            (f"skills:   🧩 {skill_count} loaded\n", "dim"),
            (f"mode:     {mode}", "dim"),
        ),
        border_style="cyan",
    ))
    console.print("[dim]Type a goal, or 'exit' to quit.[/dim]\n")


def ask_goal() -> str:
    return Prompt.ask("[bold green]you[/bold green]")


def show_thinking(text: str):
    # Text() renders dynamic content literally — never parsed as rich markup,
    # so model output containing [brackets] can't corrupt the display.
    if text.strip():
        console.print(Text("🧠 " + text.strip(), style="yellow"))


def show_action(tool_name: str, arguments: dict):
    arg_str = "  ".join(f"{k}={v!r}" for k, v in arguments.items())
    body = Text.assemble((tool_name, "bold"), ("  " + arg_str, ""))
    console.print(Panel(
        body, title="🔧 action", border_style="blue", title_align="left",
    ))


def show_result(output: str):
    console.print(Panel(
        Text(output), title="📄 result", border_style="dim", title_align="left",
    ))


def show_answer(text: str):
    console.print(Panel(
        Markdown(text or "(no answer)"),
        title="✅ answer", border_style="green", title_align="left",
    ))


def confirm(prompt: str) -> bool:
    # escape() neutralizes any [brackets] in the command being confirmed.
    answer = Prompt.ask(
        f"[bold red]⚠ {escape(prompt)}[/bold red] [dim](y/N)[/dim]",
        default="n", show_default=False,
    )
    return answer.strip().lower() in ("y", "yes")


def blocked(message: str):
    console.print(f"[red]⛔ {message}[/red]")


def info(message: str):
    console.print(f"[dim]{message}[/dim]")
