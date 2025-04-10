"""CLI commands for displaying performance metrics."""

import typer
from pytest_insight.utils.performance import (
    get_most_called_operations,
    get_performance_metrics,
    get_slowest_operations,
    reset_metrics,
)
from rich.console import Console
from rich.table import Table

console = Console()
performance = typer.Typer(
    help="Performance monitoring commands",
    context_settings={"help_option_names": ["--help", "-h"]},
)


def print_performance_metrics(top_n: int = 10, sort_by: str = "total_duration"):
    """Print performance metrics in a formatted table.

    Args:
        top_n: Number of top operations to display
        sort_by: Metric to sort by ('total_duration', 'avg_duration', 'call_count')
    """
    if sort_by == "total_duration":
        sorted_ops = get_slowest_operations(limit=top_n)
        title = f"Top {top_n} Slowest Operations (by Total Duration)"
    elif sort_by == "avg_duration":
        sorted_ops = sorted(
            get_performance_metrics().items(),
            key=lambda x: x[1]["avg_duration"],
            reverse=True,
        )[:top_n]
        title = f"Top {top_n} Slowest Operations (by Average Duration)"
    elif sort_by == "call_count":
        sorted_ops = get_most_called_operations(limit=top_n)
        title = f"Top {top_n} Most Called Operations"
    else:
        console.print(f"[red]Invalid sort_by value: {sort_by}[/red]")
        return

    if not sorted_ops:
        console.print("[yellow]No performance metrics collected yet.[/yellow]")
        return

    # Create and populate the table
    table = Table(title=title)
    table.add_column("Operation", style="cyan")
    table.add_column("Calls", justify="right", style="green")
    table.add_column("Total (s)", justify="right", style="yellow")
    table.add_column("Avg (s)", justify="right", style="yellow")
    table.add_column("Min (s)", justify="right", style="yellow")
    table.add_column("Max (s)", justify="right", style="yellow")

    for operation, metric in sorted_ops:
        table.add_row(
            operation,
            str(metric["call_count"]),
            f"{metric['total_duration']:.4f}",
            f"{metric['avg_duration']:.4f}",
            f"{metric['min_duration']:.4f}",
            f"{metric['max_duration']:.4f}",
        )

    console.print(table)


@performance.command("show")
def show(
    top: int = typer.Option(10, "--top", "-t", help="Number of top operations to display"),
    sort_by: str = typer.Option("total_duration", "--sort-by", "-s", help="Sort metric", show_choices=True),
):
    """Display performance metrics."""
    if sort_by not in ["total_duration", "avg_duration", "call_count"]:
        console.print(f"[red]Invalid sort_by value: {sort_by}[/red]")
        console.print("[yellow]Valid options are: total_duration, avg_duration, call_count[/yellow]")
        return
    print_performance_metrics(top_n=top, sort_by=sort_by)


@performance.command("analyze-showcase")
def analyze_showcase():
    """Analyze performance of showcase profile generation and loading."""
    from pytest_insight.utils.performance import get_performance_metrics, reset_metrics
    from pytest_insight.utils.trend_generator import TrendDataGenerator

    # Reset metrics to start fresh
    reset_metrics()
    console.print("[yellow]Generating showcase profile...[/yellow]")

    # Generate a showcase profile with performance monitoring
    TrendDataGenerator.create_showcase_profile(days=10)

    # Get and display performance metrics
    console.print("[green]Showcase profile generation complete.[/green]")
    console.print("[bold]Performance Analysis:[/bold]")

    # Display overall metrics
    metrics = get_performance_metrics()
    if not metrics:
        console.print("[red]No performance metrics collected.[/red]")
        return

    # Create a table for showcase profile specific operations
    table = Table(title="Showcase Profile Performance Analysis")
    table.add_column("Operation", style="cyan")
    table.add_column("Calls", justify="right", style="green")
    table.add_column("Total (s)", justify="right", style="yellow")
    table.add_column("Avg (s)", justify="right", style="yellow")
    table.add_column("% of Total", justify="right", style="red")

    # Calculate total duration of all operations
    total_duration = sum(m["total_duration"] for m in metrics.values())

    # Filter and sort operations related to showcase profile
    showcase_ops = [
        (op, metric)
        for op, metric in metrics.items()
        if any(
            x in op
            for x in [
                "create_showcase_profile",
                "_generate_sessions",
                "_create_session",
                "_generate_rerun_group",
            ]
        )
    ]
    showcase_ops.sort(key=lambda x: x[1]["total_duration"], reverse=True)

    # Add rows to the table
    for operation, metric in showcase_ops:
        percentage = (metric["total_duration"] / total_duration) * 100 if total_duration > 0 else 0
        table.add_row(
            operation,
            str(metric["call_count"]),
            f"{metric['total_duration']:.4f}",
            f"{metric['avg_duration']:.4f}",
            f"{percentage:.2f}%",
        )

    console.print(table)

    # Print recommendations
    console.print("\n[bold]Recommendations:[/bold]")
    if showcase_ops:
        slowest_op, slowest_metric = showcase_ops[0]
        console.print(
            f"[yellow]The slowest operation is [bold]{slowest_op}[/bold] "
            f"taking {slowest_metric['total_duration']:.4f}s in total.[/yellow]"
        )

        if "_generate_sessions" in slowest_op:
            console.print(
                "[green]Consider optimizing session generation by reducing the number of sessions or implementing batch processing.[/green]"
            )
        elif "_create_session" in slowest_op:
            console.print(
                "[green]Consider optimizing session creation by simplifying the data structure or implementing caching.[/green]"
            )
        elif "_generate_rerun_group" in slowest_op:
            console.print(
                "[green]Consider optimizing rerun group generation by reducing complexity or implementing parallel processing.[/green]"
            )
    else:
        console.print("[yellow]No showcase profile specific operations found in metrics.[/yellow]")


@performance.command("reset")
def reset():
    """Reset all performance metrics."""
    reset_metrics()
    console.print("[green]Performance metrics have been reset.[/green]")
