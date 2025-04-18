"""CLI commands for generating HTML reports."""

import os
from datetime import datetime
from typing import List, Optional

import typer
from pytest_insight.core.storage import get_active_profile
from pytest_insight.reports.html_report import generate_html_report
from rich.console import Console
from rich.panel import Panel

# Create report app
app = typer.Typer(
    help="Generate HTML reports for test sessions",
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.command("generate")
def generate_report(
    output_path: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Path where the HTML report will be saved. Defaults to 'pytest_insight_report_<timestamp>.html' in the current directory.",
    ),
    profile_name: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile to use (defaults to active profile)",
    ),
    session_id: Optional[List[str]] = typer.Option(
        None,
        "--session",
        "-s",
        help="Filter by session ID (can be specified multiple times)",
    ),
    days: Optional[int] = typer.Option(
        None,
        "--days",
        "-d",
        help="Include sessions from the last N days",
    ),
    title: Optional[str] = typer.Option(
        None,
        "--title",
        "-t",
        help="Custom title for the report",
    ),
    open_browser: bool = typer.Option(
        True,
        "--open/--no-open",
        help="Open the report in the default web browser after generation",
    ),
):
    """Generate an HTML report for test sessions.

    This command creates a rich HTML report with interactive visualizations
    of test results, detailed test information, and session summaries.
    """
    console = Console()

    try:
        # Get active profile if not specified
        if profile_name is None:
            profile = get_active_profile()
            profile_name = profile.name

        # Generate default output path if not specified
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"pytest_insight_report_{timestamp}.html"

        # Generate the report
        console.print(f"Generating HTML report from profile [bold]{profile_name}[/bold]...")

        # Create absolute path if relative path is provided
        if not os.path.isabs(output_path):
            output_path = os.path.abspath(output_path)

        # Generate the report
        report_path = generate_html_report(
            output_path=output_path,
            profile_name=profile_name,
            session_ids=session_id,
            days=days,
            title=title,
        )

        # Show success message
        console.print(
            Panel(
                f"HTML report generated successfully at:\n[bold]{report_path}[/bold]",
                title="Report Generation Complete",
                border_style="green",
            )
        )

        # Open the report in the default web browser if requested
        if open_browser:
            import webbrowser

            webbrowser.open(f"file://{report_path}")
            console.print("[green]Opening report in web browser...[/green]")

    except Exception as e:
        console.print(f"[bold red]Error generating report:[/bold red] {str(e)}")
        import traceback

        console.print(traceback.format_exc(), style="red")


if __name__ == "__main__":
    app()
