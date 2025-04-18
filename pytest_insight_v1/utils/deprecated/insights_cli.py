#!/usr/bin/env python3
"""
DEPRECATED: This CLI implementation has been replaced by the implementation in pytest_insight/__main__.py.

This file is kept for reference purposes only and will be removed in a future version.
Notable features that could be incorporated into the main CLI:
1. Dynamic API discovery using introspection
2. Rich formatting functions for various data types

Pytest-Insight CLI

A dynamic CLI interface for the pytest-insight API.
This CLI automatically discovers and exposes methods from the entire pytest-insight API,
including Insights, Query, Compare, and Analysis classes.
"""

import inspect
import json
from enum import Enum
from typing import Any, Dict, Optional, get_type_hints

import typer
from pytest_insight.core.analysis import Analysis
from pytest_insight.core.comparison import Comparison
from pytest_insight.core.insights import Insights
from pytest_insight.core.query import Query
from rich.box import SIMPLE
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Create Typer app
app = typer.Typer(
    name="pytest-insight",
    help="Analyze pytest test results and generate insights",
    add_completion=False,
)

# Rich console for pretty output
console = Console()


# Output format enum
class OutputFormat(str, Enum):
    TEXT = "text"
    JSON = "json"


def _get_method_info(method) -> Dict[str, Any]:
    """Extract information about a method using introspection."""
    # Get docstring
    docstring = inspect.getdoc(method) or ""

    # Get signature
    sig = inspect.signature(method)

    # Get type hints
    try:
        type_hints = get_type_hints(method)
    except Exception:
        type_hints = {}

    # Get parameter info
    params = {}
    for name, param in sig.parameters.items():
        # Skip self parameter
        if name == "self":
            continue

        param_info = {
            "name": name,
            "default": (None if param.default is inspect.Parameter.empty else param.default),
            "required": param.default is inspect.Parameter.empty,
            "type": type_hints.get(name, Any),
            "kind": str(param.kind),
        }
        params[name] = param_info

    # Get return type
    return_type = type_hints.get("return", Any)

    return {
        "docstring": docstring,
        "signature": str(sig),
        "params": params,
        "return_type": return_type,
    }


def _discover_api_methods() -> Dict[str, Dict[str, Any]]:
    """Discover all available API methods from the pytest-insight API."""
    api_methods = {}

    # Discover Insights API methods
    insights = Insights()

    # TestInsights methods
    for method_name, method in inspect.getmembers(insights.tests, predicate=inspect.ismethod):
        if method_name.startswith("_"):
            continue

        api_methods[f"insights.tests.{method_name}"] = {
            "component": "insights.tests",
            "name": method_name,
            "method_path": ["tests", method_name],
            "class_instance": "insights",
            "info": _get_method_info(method),
        }

    # SessionInsights methods
    for method_name, method in inspect.getmembers(insights.sessions, predicate=inspect.ismethod):
        if method_name.startswith("_"):
            continue

        api_methods[f"insights.sessions.{method_name}"] = {
            "component": "insights.sessions",
            "name": method_name,
            "method_path": ["sessions", method_name],
            "class_instance": "insights",
            "info": _get_method_info(method),
        }

    # TrendInsights methods
    for method_name, method in inspect.getmembers(insights.trends, predicate=inspect.ismethod):
        if method_name.startswith("_"):
            continue

        api_methods[f"insights.trends.{method_name}"] = {
            "component": "insights.trends",
            "name": method_name,
            "method_path": ["trends", method_name],
            "class_instance": "insights",
            "info": _get_method_info(method),
        }

    # Query API methods
    query = Query()
    for method_name, method in inspect.getmembers(query, predicate=inspect.ismethod):
        if method_name.startswith("_"):
            continue

        api_methods[f"query.{method_name}"] = {
            "component": "query",
            "name": method_name,
            "method_path": [method_name],
            "class_instance": "query",
            "info": _get_method_info(method),
        }

    # Comparison API methods
    compare = Comparison()
    for method_name, method in inspect.getmembers(compare, predicate=inspect.ismethod):
        if method_name.startswith("_"):
            continue

        api_methods[f"compare.{method_name}"] = {
            "component": "compare",
            "name": method_name,
            "method_path": [method_name],
            "class_instance": "compare",
            "info": _get_method_info(method),
        }

    # Analysis API methods
    analyze = Analysis()
    for method_name, method in inspect.getmembers(analyze, predicate=inspect.ismethod):
        if method_name.startswith("_"):
            continue

        api_methods[f"analyze.{method_name}"] = {
            "component": "analyze",
            "name": method_name,
            "method_path": [method_name],
            "class_instance": "analyze",
            "info": _get_method_info(method),
        }

    return api_methods


def _format_rich_output(data: Dict[str, Any], title: str = None) -> None:
    """Format data for rich console output."""
    if title:
        console.print(f"\n[bold]{title}[/bold]")

    if isinstance(data, dict):
        # Handle different data types based on content
        if "patterns" in data and isinstance(data["patterns"], list):
            # Error patterns or seasonal patterns
            _format_patterns_table(data, title)
        elif "dependencies" in data and isinstance(data["dependencies"], list):
            # Dependency graph
            _format_dependencies_table(data)
        elif "correlations" in data and isinstance(data["correlations"], list):
            # Correlation analysis
            _format_correlations_table(data)
        elif "health_score" in data:
            # Test health score
            _format_health_score(data)
        elif "environments" in data:
            # Environment impact
            _format_environment_impact(data)
        elif "timeline" in data:
            # Stability timeline
            _format_stability_timeline(data)
        else:
            # Generic dictionary output
            for key, value in data.items():
                if isinstance(value, dict):
                    console.print(f"[bold]{key}:[/bold]")
                    for subkey, subvalue in value.items():
                        console.print(f"  [cyan]{subkey}:[/cyan] {subvalue}")
                elif isinstance(value, list):
                    console.print(f"[bold]{key}:[/bold]")
                    for item in value[:10]:  # Limit to 10 items
                        if isinstance(item, dict):
                            for subkey, subvalue in item.items():
                                console.print(f"  [cyan]{subkey}:[/cyan] {subvalue}")
                            console.print("")
                        else:
                            console.print(f"  {item}")
                    if len(value) > 10:
                        console.print(f"  [dim]...and {len(value) - 10} more items[/dim]")
                else:
                    console.print(f"[bold]{key}:[/bold] {value}")
    elif isinstance(data, list):
        # List output
        for item in data[:20]:  # Limit to 20 items
            if isinstance(item, dict):
                for key, value in item.items():
                    console.print(f"[cyan]{key}:[/cyan] {value}")
                console.print("")
            else:
                console.print(f"- {item}")
        if len(data) > 20:
            console.print(f"[dim]...and {len(data) - 20} more items[/dim]")
    else:
        # Simple output
        console.print(data)


def _format_patterns_table(data: Dict[str, Any], title: str) -> None:
    """Format patterns data as a table."""
    patterns = data.get("patterns", [])
    if not patterns:
        console.print("[yellow]No significant patterns identified in the dataset.[/yellow]")
        return

    if "error_patterns" in title.lower():
        # Error patterns table
        table = Table(title=title, box=SIMPLE)
        table.add_column("Pattern", style="cyan")
        table.add_column("Count", style="yellow")
        table.add_column("Affected Tests", style="red")

        for pattern in patterns[:10]:  # Limit to top 10
            table.add_row(
                pattern.get("pattern", "Unknown"),
                str(pattern.get("count", 0)),
                str(len(pattern.get("affected_tests", []))),
            )
    else:
        # Seasonal patterns table
        table = Table(title=title, box=SIMPLE)
        table.add_column("Test", style="cyan")
        table.add_column("Total Failures", style="red")
        table.add_column("Time of Day Pattern", style="yellow")
        table.add_column("Day of Week Pattern", style="green")

        # Map day numbers to names
        day_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        for pattern in patterns[:10]:  # Limit to top 10
            # Format time of day patterns
            hour_pattern = ""
            if pattern.get("peak_hours"):
                hour_pattern = ", ".join(
                    [f"{hour}:00 ({int(pct*100)}%)" for hour, count, pct in pattern.get("peak_hours", [])]
                )
            else:
                hour_pattern = "No significant pattern"

            # Format day of week patterns
            day_pattern = ""
            if pattern.get("peak_days"):
                day_pattern = ", ".join(
                    [f"{day_names[day]} ({int(pct*100)}%)" for day, count, pct in pattern.get("peak_days", [])]
                )
            else:
                day_pattern = "No significant pattern"

            table.add_row(
                pattern.get("test_short", "Unknown"),
                str(pattern.get("total_failures", 0)),
                hour_pattern,
                day_pattern,
            )

    console.print(table)


def _format_dependencies_table(data: Dict[str, Any]) -> None:
    """Format dependency graph data as a table."""
    dependencies = data.get("dependencies", [])
    if not dependencies:
        console.print("[yellow]No significant dependencies identified in the dataset.[/yellow]")
        return

    table = Table(title="Test Dependency Analysis", box=SIMPLE)
    table.add_column("Test Relationship", style="cyan")
    table.add_column("Strength", style="yellow")
    table.add_column("Co-Failures", style="red")
    table.add_column("Interpretation", style="green")

    for dep in dependencies[:10]:  # Limit to top 10
        # Format test names to be shorter
        test1_short = dep.get("test1", "").split("::")[-1]
        test2_short = dep.get("test2", "").split("::")[-1]

        if "→" in dep.get("direction", ""):
            relationship = f"{test1_short} → {test2_short}"
        elif "↔" in dep.get("direction", ""):
            relationship = f"{test1_short} ↔ {test2_short}"
        else:
            relationship = f"{test1_short} - {test2_short}"

        table.add_row(
            relationship,
            f"{dep.get('strength', 0):.2f}",
            str(dep.get("co_failure_count", 0)),
            dep.get("interpretation", "Unknown"),
        )

    console.print(table)


def _format_correlations_table(data: Dict[str, Any]) -> None:
    """Format correlation analysis data as a table."""
    correlations = data.get("correlations", [])
    if not correlations:
        console.print("[yellow]No significant correlations identified in the dataset.[/yellow]")
        return

    table = Table(title="Test Correlation Analysis", box=SIMPLE)
    table.add_column("Test Pair", style="cyan")
    table.add_column("Correlation", style="yellow")
    table.add_column("Relationship", style="green")
    table.add_column("Strength", style="red")

    for corr in correlations[:10]:  # Limit to top 10
        test1_short = corr.get("test1_short", "Unknown")
        test2_short = corr.get("test2_short", "Unknown")

        table.add_row(
            f"{test1_short} - {test2_short}",
            f"{corr.get('correlation', 0):.2f}",
            corr.get("relationship", "Unknown"),
            f"{corr.get('strength', 0):.2f}",
        )

    console.print(table)


def _format_health_score(data: Dict[str, Any]) -> None:
    """Format health score data."""
    health_score = data.get("health_score", 0)

    # Determine color based on score
    if health_score >= 80:
        health_color = "green"
    elif health_score >= 60:
        health_color = "yellow"
    else:
        health_color = "red"

    console.print(f"[bold]Test Health Score:[/bold] [{health_color}]{health_score:.1f}/100[/{health_color}]")

    # Display brittle tests
    brittle_tests = data.get("brittle_tests", [])
    if brittle_tests:
        console.print("\n[bold]Most Brittle Tests:[/bold]")
        table = Table(box=SIMPLE)
        table.add_column("Test", style="cyan")
        table.add_column("Brittleness Score", style="red")
        table.add_column("Pass Rate", style="yellow")
        table.add_column("Duration Stability", style="green")

        for test in brittle_tests[:10]:  # Limit to top 10
            test_short = test.get("test_id", "Unknown").split("::")[-1]
            table.add_row(
                test_short,
                f"{test.get('brittleness_score', 0):.2f}",
                f"{test.get('pass_rate', 0):.2%}",
                f"{test.get('duration_stability', 0):.2f}",
            )

        console.print(table)


def _format_environment_impact(data: Dict[str, Any]) -> None:
    """Format environment impact data."""
    environments = data.get("environments", {})
    if not environments:
        console.print("[yellow]No environment data available.[/yellow]")
        return

    table = Table(title="Environment Impact Analysis", box=SIMPLE)
    table.add_column("Environment", style="cyan")
    table.add_column("Pass Rate", style="green")
    table.add_column("Test Count", style="yellow")
    table.add_column("Avg Duration", style="blue")

    for env_name, env_data in environments.items():
        pass_rate = env_data.get("pass_rate", 0)
        test_count = env_data.get("test_count", 0)
        avg_duration = env_data.get("avg_duration", 0)

        table.add_row(env_name, f"{pass_rate:.2%}", str(test_count), f"{avg_duration:.2f}s")

    console.print(table)

    # Display consistency score
    consistency = data.get("consistency", 0)
    console.print(f"[bold]Environment Consistency Score:[/bold] {consistency:.2f}")


def _format_stability_timeline(data: Dict[str, Any]) -> None:
    """Format stability timeline data."""
    timeline = data.get("timeline", {})
    dates = data.get("dates", [])
    trends = data.get("trends", {})

    if not timeline or not dates:
        console.print("[yellow]No stability timeline data available.[/yellow]")
        return

    table = Table(title="Test Stability Timeline", box=SIMPLE)
    table.add_column("Test", style="cyan", width=30)

    # Add date columns
    for date in dates:
        table.add_column(date.strftime("%Y-%m-%d"), style="yellow")

    # Add trend column
    table.add_column("Trend", style="green")

    # Add rows for each test
    for nodeid in timeline:
        test_short = nodeid.split("::")[-1] if "::" in nodeid else nodeid
        row = [test_short]

        # Add stability score for each date
        for date in dates:
            if date in timeline[nodeid]:
                metrics = timeline[nodeid][date]
                stability = metrics.get("stability_score", 0)

                # Format cell with stability score and color
                if stability >= 0.9:
                    cell = f"[green]{stability:.2f}[/green]"
                elif stability >= 0.7:
                    cell = f"[yellow]{stability:.2f}[/yellow]"
                else:
                    cell = f"[red]{stability:.2f}[/red]"

                # Add run count
                cell += f" ({metrics.get('total_runs', 0)})"
            else:
                cell = "-"

            row.append(cell)

        # Add trend
        trend_info = trends.get(nodeid, {})
        direction = trend_info.get("direction", "insufficient_data")

        if direction == "improving":
            trend = "[green]↑ Improving[/green]"
        elif direction == "declining":
            trend = "[red]↓ Declining[/red]"
        elif direction == "stable":
            trend = "[blue]→ Stable[/blue]"
        else:
            trend = "Insufficient data"

        row.append(trend)
        table.add_row(*row)

    console.print(table)


def _create_dynamic_command(method_info: Dict[str, Any]):
    """Create a dynamic Typer command based on method info."""
    component = method_info["component"]
    method_name = method_info["name"]
    info = method_info["info"]
    class_instance = method_info["class_instance"]
    method_path = method_info["method_path"]

    # Create command function
    def command_func(
        data_path: Optional[str] = typer.Option(None, "--data-path", "-d", help="Path to test data"),
        sut_filter: Optional[str] = typer.Option(None, "--sut", "-s", help="Filter by system under test"),
        days: Optional[int] = typer.Option(None, "--days", help="Filter by number of days"),
        test_pattern: Optional[str] = typer.Option(None, "--test", "-t", help="Filter by test name pattern"),
        profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Storage profile to use"),
        output_format: OutputFormat = typer.Option(
            OutputFormat.TEXT, "--format", "-f", help="Output format (text or json)"
        ),
        **kwargs,
    ):
        """Dynamic command function."""
        # Create insights instance
        if class_instance == "insights":
            insights = Insights(profile_name=profile)
        elif class_instance == "query":
            insights = Query(profile_name=profile)
        elif class_instance == "compare":
            insights = Comparison(profile_name=profile)
        elif class_instance == "analyze":
            insights = Analysis(profile_name=profile)

        # Apply filters if provided
        if any([sut_filter, days, test_pattern]):
            insights = insights.with_query(lambda q: q.filter_by_sut(sut_filter) if sut_filter else q)
            insights = insights.with_query(lambda q: q.in_last_days(days) if days else q)
            insights = insights.with_query(lambda q: q.filter_by_test_name(test_pattern) if test_pattern else q)

        # Get the component
        if class_instance == "insights":
            component_obj = getattr(insights, method_path[0])
            method = getattr(component_obj, method_path[1])
        else:
            method = getattr(insights, method_path[0])

        # Extract method-specific parameters from kwargs
        method_params = {}
        for param_name, param_info in info["params"].items():
            if param_name in kwargs:
                method_params[param_name] = kwargs[param_name]

        # Call the method
        result = method(**method_params)

        # Output the result
        if output_format == OutputFormat.JSON:
            console.print(json.dumps(result, default=str, indent=2))
        else:
            _format_rich_output(
                result,
                title=f"{component.capitalize()} {method_name.replace('_', ' ').title()}",
            )

    # Update function metadata
    command_func.__name__ = f"{component}_{method_name}"
    command_func.__doc__ = info["docstring"]

    # Add command-specific options
    for param_name, param_info in info["params"].items():
        # Skip parameters that are already handled
        if param_name in [
            "data_path",
            "sut_filter",
            "days",
            "test_pattern",
            "profile",
            "output_format",
        ]:
            continue

        # Add option to command
        typer.Option(
            param_info["default"],
            f"--{param_name.replace('_', '-')}",
            help=f"{param_name} parameter",
        )

    return command_func


# Create dynamic commands for all API methods
api_methods = _discover_api_methods()
for method_key, method_info in api_methods.items():
    command_func = _create_dynamic_command(method_info)
    # Use a more readable command name format
    command_name = method_key.replace(".", "-")
    app.command(name=command_name)(command_func)


@app.command()
def summary(
    data_path: Optional[str] = typer.Option(None, "--data-path", "-d", help="Path to test data"),
    sut_filter: Optional[str] = typer.Option(None, "--sut", "-s", help="Filter by system under test"),
    days: Optional[int] = typer.Option(None, "--days", help="Filter by number of days"),
    test_pattern: Optional[str] = typer.Option(None, "--test", "-t", help="Filter by test name pattern"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Storage profile to use"),
    output_format: OutputFormat = typer.Option(
        OutputFormat.TEXT, "--format", "-f", help="Output format (text or json)"
    ),
):
    """Generate a comprehensive summary report of all insights."""
    # Create insights instance with data path if provided
    if data_path:
        # Create an Analysis instance with the data path
        analysis_instance = Analysis()
        # TODO: Implement loading data from file path
        insights = Insights(analysis=analysis_instance, profile_name=profile)
    else:
        # When using a profile, we need to load sessions from storage
        if profile:
            # Create a Query to get all sessions
            query = Query(profile_name=profile)
            # Execute the query to get sessions
            query_result = query.execute()
            # Create an Analysis with the sessions
            analysis_instance = Analysis(sessions=query_result.sessions, profile_name=profile)
            insights = Insights(analysis=analysis_instance)
        else:
            insights = Insights(profile_name=profile)

    # Apply filters if provided
    if any([sut_filter, days, test_pattern]):
        insights = insights.with_query(lambda q: q.filter_by_sut(sut_filter) if sut_filter else q)
        insights = insights.with_query(lambda q: q.in_last_days(days) if days else q)
        insights = insights.with_query(lambda q: q.filter_by_test_name(test_pattern) if test_pattern else q)

    # Generate summary report
    result = insights.summary_report()

    # Output the result
    if output_format == OutputFormat.JSON:
        console.print(json.dumps(result, default=str, indent=2))
    else:
        console.print(Panel("[bold]Pytest-Insight Summary Report[/bold]"))

        # Display health metrics
        health = result.get("health", {})
        if health:
            console.print("\n[bold]Health Metrics[/bold]")

            health_score_data = health.get("health_score", {})
            health_score = health_score_data.get("overall_score", 0)
            if health_score >= 80:
                health_color = "green"
            elif health_score >= 60:
                health_color = "yellow"
            else:
                health_color = "red"

            console.print(f"Health Score: [{health_color}]{health_score:.1f}/100[/{health_color}]")
            console.print(f"Pass Rate: {health.get('pass_rate', 0):.2%}")
            console.print(f"Flaky Tests: {health.get('flaky_test_count', 0)}")
            console.print(f"Slow Tests: {health.get('slow_test_count', 0)}")

        # Display test insights
        test_insights = result.get("test_insights", {})
        if test_insights:
            console.print("\n[bold]Test Insights[/bold]")

            # Display top error patterns
            error_patterns = test_insights.get("error_patterns", [])
            if error_patterns:
                console.print("\n[bold]Top Error Patterns:[/bold]")
                for i, pattern in enumerate(error_patterns[:3]):
                    console.print(f"{i+1}. {pattern.get('pattern', 'Unknown')} ({pattern.get('count', 0)} occurrences)")

            # Display test dependencies
            dependencies = test_insights.get("dependencies", [])
            if dependencies:
                console.print("\n[bold]Top Test Dependencies:[/bold]")
                for i, dep in enumerate(dependencies[:3]):
                    test1 = dep.get("test1", "").split("::")[-1]
                    test2 = dep.get("test2", "").split("::")[-1]
                    console.print(f"{i+1}. {test1} → {test2} (strength: {dep.get('strength', 0):.2f})")

        # Display session insights
        session_insights = result.get("session_insights", {})
        if session_insights:
            console.print("\n[bold]Session Insights[/bold]")

            # Display environment impact
            env_impact = session_insights.get("environment_impact", {})
            if env_impact:
                console.print("\n[bold]Environment Impact:[/bold]")
                environments = env_impact.get("environments", {})
                for env_name, env_data in list(environments.items())[:3]:
                    console.print(f"{env_name}: {env_data.get('pass_rate', 0):.2%} pass rate")

        # Display trend insights
        trend_insights = result.get("trend_insights", {})
        if trend_insights:
            console.print("\n[bold]Trend Insights[/bold]")

            # Display failure trends
            failure_trends = trend_insights.get("failure_trends", {})
            if failure_trends:
                trend_pct = failure_trends.get("trend_percentage", 0)
                improving = failure_trends.get("improving", False)

                if improving:
                    console.print(f"Failure rate is [green]improving by {abs(trend_pct):.1f}%[/green]")
                else:
                    console.print(f"Failure rate is [red]worsening by {abs(trend_pct):.1f}%[/red]")


@app.command()
def list_commands():
    """List all available commands with descriptions."""
    console.print("[bold]Available Commands:[/bold]")

    # Group commands by component
    commands_by_component = {}
    for method_key, method_info in api_methods.items():
        component = method_info["component"]
        if component not in commands_by_component:
            commands_by_component[component] = []

        commands_by_component[component].append(
            {
                "name": method_key.replace(".", "-"),
                "description": method_info["info"]["docstring"].split("\n")[0],
            }
        )

    # Display commands by component
    for component, commands in commands_by_component.items():
        console.print(f"\n[bold]{component.capitalize()}[/bold]")
        for command in commands:
            console.print(f"  [cyan]{command['name']}[/cyan]: {command['description']}")

    # Display built-in commands
    console.print("\n[bold]Built-in Commands[/bold]")
    console.print("  [cyan]summary[/cyan]: Generate a comprehensive summary report of all insights")
    console.print("  [cyan]list-commands[/cyan]: List all available commands with descriptions")


if __name__ == "__main__":
    app()
