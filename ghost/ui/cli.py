"""Rich CLI with interactive menus and progress tracking."""

import asyncio
import importlib.util
import shutil
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.prompt import Prompt, Confirm
from rich.tree import Tree
from rich.text import Text
from rich import box

from ghost.core.investigator import GhostInvestigator
from ghost.core.config import config
from ghost.backend.db import DB_PATH, get_connection, init_db

console = Console()

BANNER = """
 ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗
██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝
██║  ███╗███████║██║   ██║███████╗   ██║
██║   ██║██╔══██║██║   ██║╚════██║   ██║
╚██████╔╝██║  ██║╚██████╔╝███████║   ██║
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝
    AI-Powered OSINT Investigation Platform
"""

DISCLAIMER = (
    "[bold red]LEGAL DISCLAIMER:[/bold red] This tool is for authorized use only. "
    "Unauthorized surveillance, stalking, or privacy violation is illegal. "
    "You are solely responsible for lawful use."
)


def print_banner():
    console.print(Panel(
        Text(BANNER, style="bold green", justify="center"),
        border_style="green",
        padding=(0, 2),
    ))
    console.print(DISCLAIMER, justify="center")
    console.print()


def create_progress():
    return Progress(
        SpinnerColumn(style="green"),
        TextColumn("[bold green]{task.description}"),
        BarColumn(bar_width=30, style="green", complete_style="bold green"),
        TextColumn("[dim]{task.fields[status]}"),
        TimeElapsedColumn(),
        console=console,
    )


@click.group(invoke_without_command=True)
@click.option("--target", "-t", help="Investigation target")
@click.option("--type", "-T", "input_type", default="auto", help="Input type: username/email/phone/domain/image/auto")
@click.option("--modules", "-m", help="Comma-separated modules to run")
@click.option("--output", "-o", help="Output file path")
@click.option("--format", "-f", "fmt", default="html", help="Report format: html/pdf/json")
@click.pass_context
def cli(ctx, target, input_type, modules, output, fmt):
    """Ghost — AI-Powered OSINT Investigation Platform"""
    if ctx.invoked_subcommand is not None:
        return

    print_banner()

    if target:
        # Direct investigation mode
        module_list = modules.split(",") if modules else None
        run_investigation(target, input_type, module_list, output, fmt)
    else:
        # Interactive mode
        interactive_menu()


@cli.command()
@click.argument("target")
@click.option("--type", "-T", "input_type", default="auto")
@click.option("--modules", "-m", help="Comma-separated modules")
@click.option("--output", "-o")
@click.option("--format", "-f", "fmt", default="html")
def investigate(target, input_type, modules, output, fmt):
    """Run an investigation on a target."""
    print_banner()
    module_list = modules.split(",") if modules else None
    run_investigation(target, input_type, module_list, output, fmt)


@cli.command()
def interactive():
    """Launch interactive investigation mode."""
    print_banner()
    interactive_menu()


@cli.command()
def doctor():
    """Check local Ghost configuration and optional capabilities."""
    print_banner()

    table = Table(title="Ghost Doctor", box=box.ROUNDED, border_style="green")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail", overflow="fold")

    def add(name: str, ok: bool, detail: str):
        table.add_row(name, "[green]OK[/green]" if ok else "[yellow]WARN[/yellow]", detail)

    try:
        init_db()
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        add("database", True, str(DB_PATH))
    except Exception as exc:
        add("database", False, str(exc))

    add("OpenAI key", config.has_api_key("openai_api_key"), "set" if config.has_api_key("openai_api_key") else "missing; fallback summaries still work")

    for package, label in [
        ("aiohttp", "HTTP collection"),
        ("rich", "CLI UI"),
        ("flask", "REST API"),
        ("phonenumbers", "Phone module"),
        ("dns", "Domain DNS module"),
    ]:
        add(label, importlib.util.find_spec(package) is not None, package)

    for binary, label in [("sherlock", "Sherlock optional username coverage")]:
        found = shutil.which(binary)
        add(label, bool(found), found or "not installed; built-in platform checks still run")

    add("enabled modules", bool(config.enabled_modules), ", ".join(config.enabled_modules))
    console.print(table)


def interactive_menu():
    """Interactive menu for investigations."""
    while True:
        console.print()
        console.print(Panel(
            "[bold green]INVESTIGATION MENU[/bold green]",
            border_style="green",
            padding=(0, 2),
        ))

        table = Table(show_header=False, box=box.SIMPLE, border_style="green")
        table.add_column(style="bold green", width=6)
        table.add_column(style="white")
        table.add_row("[1]", "Username Investigation")
        table.add_row("[2]", "Email Investigation")
        table.add_row("[3]", "Phone Number Investigation")
        table.add_row("[4]", "Domain Investigation")
        table.add_row("[5]", "Image Analysis")
        table.add_row("[6]", "Full Investigation (all modules)")
        table.add_row("[7]", "Custom Module Selection")
        table.add_row("[0]", "Exit")
        console.print(table)

        choice = Prompt.ask("[green]Select option", choices=["0", "1", "2", "3", "4", "5", "6", "7"], default="1")

        if choice == "0":
            console.print("[dim]Exiting Ghost...[/dim]")
            sys.exit(0)

        type_map = {
            "1": "username",
            "2": "email",
            "3": "phone",
            "4": "domain",
            "5": "image",
            "6": "auto",
            "7": "auto",
        }

        input_type = type_map[choice]
        target = Prompt.ask(f"[green]Enter {input_type if input_type != 'auto' else 'target'}")

        if not target.strip():
            console.print("[red]No target provided.[/red]")
            continue

        modules = None
        if choice == "7":
            console.print(f"[dim]Available modules: {', '.join(config.enabled_modules)}[/dim]")
            mod_input = Prompt.ask("[green]Enter modules (comma-separated)")
            modules = [m.strip() for m in mod_input.split(",")]

        fmt = Prompt.ask("[green]Report format", choices=["html", "pdf", "json"], default="html")

        if Confirm.ask(f"[green]Start investigation on [bold]{target}[/bold]?", default=True):
            run_investigation(target, input_type, modules, None, fmt)


def run_investigation(target: str, input_type: str, modules: list = None, output: str = None, fmt: str = "html"):
    """Execute an investigation with progress display."""
    investigator = GhostInvestigator()

    console.print()
    console.print(Panel(
        f"[bold green]TARGET:[/bold green] {target}\n"
        f"[bold green]TYPE:[/bold green] {input_type}\n"
        f"[bold green]MODULES:[/bold green] {', '.join(modules) if modules else 'auto'}",
        title="[bold green]INVESTIGATION STARTING[/bold green]",
        border_style="green",
    ))
    console.print()

    # Progress tracking
    module_tasks = {}

    with create_progress() as progress:
        main_task = progress.add_task("Investigation", total=100, status="initializing...")

        def progress_callback(module, status, detail):
            if module == "complete":
                progress.update(main_task, completed=100, status="Complete!")
                return

            if module not in module_tasks:
                module_tasks[module] = progress.add_task(
                    f"  {module}", total=100, status=status
                )

            if status == "done":
                progress.update(module_tasks[module], completed=100, status=detail)
            elif status == "error":
                progress.update(module_tasks[module], completed=100, status=f"[red]{detail}[/red]")
            else:
                progress.update(module_tasks[module], completed=50, status=detail)

            # Update main progress
            done_count = sum(1 for m in module_tasks.values() if progress.tasks[m].completed >= 100)
            total_modules = max(len(module_tasks), 1)
            progress.update(main_task, completed=int(done_count / total_modules * 90), status=f"{done_count}/{total_modules} modules")

        investigator.set_progress_callback(progress_callback)

        # Run the investigation
        investigation = asyncio.run(
            investigator.investigate_async(target, input_type, modules)
        )

    console.print()

    # Display results
    display_results(investigation)

    # Generate report
    report_path = investigator.generate_report(investigation, fmt, output)
    console.print()
    console.print(Panel(
        f"[bold green]Report saved to:[/bold green] {report_path}",
        border_style="green",
    ))


def display_results(investigation):
    """Display investigation results in a rich format."""
    inv = investigation.to_dict()

    # Summary
    if inv.get("summary"):
        console.print(Panel(
            inv["summary"],
            title="[bold green]EXECUTIVE SUMMARY[/bold green]",
            border_style="green",
        ))

    # Risk Score
    risk = inv.get("risk_score", 0)
    risk_color = "green" if risk < 0.4 else "yellow" if risk < 0.7 else "red"
    console.print(Panel(
        f"[bold {risk_color}]Risk Score: {risk:.0%}[/bold {risk_color}]",
        border_style=risk_color,
    ))

    # Findings tree
    tree = Tree("[bold green]Investigation Findings[/bold green]")
    for module, data in inv.get("findings", {}).items():
        if isinstance(data, dict) and "error" not in data:
            branch = tree.add(f"[green]{module}[/green]")
            _add_dict_to_tree(branch, data, depth=0, max_depth=2)
        elif isinstance(data, dict) and "error" in data:
            tree.add(f"[red]{module}: {data['error']}[/red]")

    console.print(tree)

    # Errors
    if inv.get("errors"):
        console.print()
        err_table = Table(title="Errors", border_style="red", box=box.ROUNDED)
        err_table.add_column("Error", style="red")
        for err in inv["errors"]:
            err_table.add_row(str(err))
        console.print(err_table)


def _add_dict_to_tree(tree, data, depth=0, max_depth=2):
    """Recursively add dict data to a Rich tree."""
    if depth >= max_depth:
        return

    if isinstance(data, dict):
        for key, val in data.items():
            if key in ("raw", "all_tags", "encoding"):
                continue
            if isinstance(val, dict):
                branch = tree.add(f"[dim]{key}:[/dim]")
                _add_dict_to_tree(branch, val, depth + 1, max_depth)
            elif isinstance(val, list):
                if len(val) == 0:
                    tree.add(f"[dim]{key}:[/dim] []")
                elif len(val) <= 3:
                    branch = tree.add(f"[dim]{key}:[/dim]")
                    for item in val:
                        if isinstance(item, dict):
                            sub = branch.add("")
                            _add_dict_to_tree(sub, item, depth + 1, max_depth)
                        else:
                            branch.add(str(item)[:100])
                else:
                    tree.add(f"[dim]{key}:[/dim] [{len(val)} items]")
            else:
                val_str = str(val)[:100]
                tree.add(f"[dim]{key}:[/dim] {val_str}")


def main():
    cli()


if __name__ == "__main__":
    main()
