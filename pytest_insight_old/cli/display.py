from typing import Any, Dict

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


class ResultsDisplay:
    """Handle all CLI display formatting."""

    @staticmethod
    def show_failure_patterns(patterns: Dict[str, Any]) -> None:
        """Display failure pattern analysis."""
        console.print("\n[bold blue]=== Failure Pattern Analysis ===\n")

        # Most Failed Tests Table
        table = Table(title="Most Failed Tests")
        table.add_column("Test", style="cyan")
        table.add_column("Failures", justify="right", style="red")

        for test in patterns["most_failed"]:
            table.add_row(test["nodeid"], str(test["failure_count"]))

        console.print(table)

        # Timing Related Failures Table
        if patterns["timing_related"]:
            timing_table = Table(title="Timing Related Failures")
            timing_table.add_column("Test", style="cyan")
            timing_table.add_column("Avg Duration", justify="right", style="yellow")

            for test in patterns["timing_related"]:
                timing_table.add_row(test["nodeid"], f"{test['avg_duration']:.2f}s")

            console.print("\n", timing_table)

    @staticmethod
    def show_trend_analysis(analysis: Dict[str, Any]) -> None:
        """Display trend analysis results."""
        if analysis["duration_trend"]["trend"] == "insufficient_data":
            console.print("[yellow]No test data found in specified timespan[/yellow]")
            return

        # Create panel for trend analysis
        content = Text()
        content.append("\nDuration Trends\n", style="bold cyan")

        trend = analysis["duration_trend"]["trend"]
        trend_style = {
            "increasing": "red",
            "decreasing": "green",
            "stable": "yellow",
        }.get(trend, "white")

        content.append("Direction: ", style="dim")
        content.append(trend, style=trend_style)

        content.append("\n\nFailure Rate\n", style="bold red")
        content.append(f"{analysis['failure_rate']:.1%}", style="red")

        panel = Panel(content, title="[bold blue]Trend Analysis", border_style="blue")
        console.print(panel)

    @staticmethod
    def show_test_history(history: Dict[str, Any]) -> None:
        """Display test execution history."""
        # Create main panel content
        content = Text()
        content.append("\nTest: ", style="dim")
        content.append(history["nodeid"], style="cyan")

        content.append("\n\nTotal Executions: ", style="dim")
        content.append(str(history["total_runs"]), style="green")

        content.append("\nFailure Rate: ", style="dim")
        rate_style = "red" if history["failure_rate"] > 0.2 else "green"
        content.append(f"{history['failure_rate']:.1%}", style=rate_style)

        panel = Panel(content, title="[bold blue]Test History", border_style="blue")

        # Create warnings table if any exist
        if history.get("warnings"):
            warning_table = Table(title="Test Warnings")
            warning_table.add_column("Time", style="yellow")
            warning_table.add_column("Message", style="white")

            for warn in history["warnings"]:
                warning_table.add_row(warn["timestamp"].strftime("%Y-%m-%d %H:%M"), warn["message"])

            # Layout with both panels
            layout = Layout()
            layout.split_column(Layout(panel), Layout(warning_table))
            console.print(layout)
        else:
            console.print(panel)

    @staticmethod
    def show_comparison(comparison: Dict[str, Any]) -> None:
        """Display comparison analysis results."""
        # Summary table
        summary = Table(title="Comparison Summary")
        summary.add_column("Metric", style="cyan")
        summary.add_column("Base", justify="right")
        summary.add_column("Target", justify="right")
        summary.add_column("Difference", justify="right")

        for metric in comparison["metrics"]:
            base_val = metric["base_value"]
            target_val = metric["target_value"]
            diff = target_val - base_val
            diff_style = "red" if diff > 0 else "green"

            summary.add_row(
                metric["name"],
                f"{base_val:.2f}",
                f"{target_val:.2f}",
                Text(f"{diff:+.2f}", style=diff_style),
            )

        console.print(summary)
