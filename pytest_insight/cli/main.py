#!/usr/bin/env python
"""Main entry point for the pytest-insight CLI."""

import traceback

import typer
from rich.console import Console

# Create the main CLI app
app = typer.Typer(help="Command-line interface for pytest-insight")

# Import the CLI modules
from pytest_insight.cli.cli import app as main_cli
from pytest_insight.cli.cli_dev import app as dev_cli

# Add the CLI modules as subcommands
app.add_typer(main_cli, name="core")
app.add_typer(dev_cli, name="dev")

# Main entry point
if __name__ == "__main__":
    try:
        app()
    except Exception as e:
        console = Console()
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        console.print(traceback.format_exc(), style="red")
