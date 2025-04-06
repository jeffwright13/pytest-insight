#!/usr/bin/env python3
"""
Developer CLI for pytest-insight.

This CLI provides a dynamic interface for exploring the pytest-insight API.
It automatically discovers and exposes all methods from the API classes,
making it easy to explore functionality and test new features.
"""

import inspect
import json
from enum import Enum
from typing import Any, Dict, Optional, get_type_hints

import typer
from rich.box import SIMPLE
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pytest_insight.core.analysis import Analysis
from pytest_insight.core.comparison import Comparison
from pytest_insight.core.insights import Insights
from pytest_insight.core.query import Query

# Create Typer app
app = typer.Typer(
    name="pytest-insight-dev",
    help="Developer CLI for exploring the pytest-insight API",
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
            "default": (
                None if param.default is inspect.Parameter.empty else param.default
            ),
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
    for method_name, method in inspect.getmembers(
        insights.tests, predicate=inspect.ismethod
    ):
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
    for method_name, method in inspect.getmembers(
        insights.sessions, predicate=inspect.ismethod
    ):
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
    for method_name, method in inspect.getmembers(
        insights.trends, predicate=inspect.ismethod
    ):
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
        # Handle dictionary output
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
                    console.print(
                        f"  [dim]...and {len(value) - 10} more items[/dim]"
                    )
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


def _create_dynamic_command(method_info: Dict[str, Any]):
    """Create a dynamic Typer command based on method info."""
    component = method_info["component"]
    method_name = method_info["name"]
    info = method_info["info"]
    class_instance = method_info["class_instance"]
    method_path = method_info["method_path"]

    # Create command function
    def command_func(
        data_path: Optional[str] = typer.Option(
            None, "--data-path", "-d", help="Path to test data"
        ),
        sut_filter: Optional[str] = typer.Option(
            None, "--sut", "-s", help="Filter by system under test"
        ),
        days: Optional[int] = typer.Option(
            None, "--days", help="Filter by number of days"
        ),
        test_pattern: Optional[str] = typer.Option(
            None, "--test", "-t", help="Filter by test name pattern"
        ),
        profile: Optional[str] = typer.Option(
            None, "--profile", "-p", help="Storage profile to use"
        ),
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
            insights = insights.with_query(
                lambda q: q.filter_by_sut(sut_filter) if sut_filter else q
            )
            insights = insights.with_query(
                lambda q: q.in_last_days(days) if days else q
            )
            insights = insights.with_query(
                lambda q: q.filter_by_test_name(test_pattern) if test_pattern else q
            )

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

    return command_func


@app.command("list-api")
def list_api_methods():
    """List all available API methods."""
    api_methods = _discover_api_methods()
    
    # Group methods by component
    methods_by_component = {}
    for key, method_info in api_methods.items():
        component = method_info["component"]
        if component not in methods_by_component:
            methods_by_component[component] = []
        methods_by_component[component].append((key, method_info))
    
    # Display methods grouped by component
    for component, methods in sorted(methods_by_component.items()):
        console.print(f"\n[bold]{component.upper()}[/bold]")
        
        component_table = Table(box=SIMPLE, show_header=True)
        component_table.add_column("Method", style="cyan")
        component_table.add_column("Description", style="green")
        component_table.add_column("Parameters", style="yellow")
        
        for key, method_info in sorted(methods, key=lambda x: x[1]["name"]):
            # Get first line of docstring as description
            docstring = method_info["info"]["docstring"]
            description = docstring.split("\n")[0] if docstring else "No description"
            
            # Format parameters
            params = method_info["info"]["params"]
            if not params:
                param_str = "None"
            else:
                param_items = []
                for name, param_info in params.items():
                    # Get type name in a readable format
                    param_type = param_info["type"]
                    if hasattr(param_type, "__name__"):
                        type_str = param_type.__name__
                    else:
                        type_str = str(param_type).replace("typing.", "")
                    
                    # Format with required/optional and default value
                    if param_info["required"]:
                        param_items.append(f"{name}: {type_str} (required)")
                    else:
                        default = param_info["default"]
                        default_str = str(default) if default is not None else "None"
                        param_items.append(f"{name}: {type_str} = {default_str}")
                
                param_str = "\n".join(param_items)
            
            component_table.add_row(
                method_info["name"],
                description,
                param_str
            )
        
        console.print(component_table)


@app.command("show-method")
def show_method_details(method_path: str = typer.Argument(..., help="Method path (e.g., insights.tests.flaky_tests)")):
    """Show detailed information about a specific API method."""
    api_methods = _discover_api_methods()
    
    if method_path not in api_methods:
        console.print(f"[bold red]Method '{method_path}' not found.[/bold red]")
        # Show similar methods as suggestions
        similar_methods = [m for m in api_methods.keys() if method_path.split(".")[-1] in m]
        if similar_methods:
            console.print("\n[bold]Similar methods:[/bold]")
            for m in similar_methods:
                console.print(f"  {m}")
        return
    
    method_info = api_methods[method_path]
    info = method_info["info"]
    
    # Create a panel with method details
    panel_content = []
    panel_content.append(f"[bold cyan]Method:[/bold cyan] {method_path}")
    panel_content.append("")
    
    # Add docstring
    if info["docstring"]:
        panel_content.append("[bold]Description:[/bold]")
        panel_content.append(info["docstring"])
        panel_content.append("")
    
    # Add signature
    panel_content.append(f"[bold]Signature:[/bold] {info['signature']}")
    panel_content.append("")
    
    # Add parameters
    if info["params"]:
        panel_content.append("[bold]Parameters:[/bold]")
        for name, param_info in info["params"].items():
            # Get type name in a readable format
            param_type = param_info["type"]
            if hasattr(param_type, "__name__"):
                type_str = param_type.__name__
            else:
                type_str = str(param_type).replace("typing.", "")
            
            # Format with required/optional and default value
            if param_info["required"]:
                panel_content.append(f"  [cyan]{name}[/cyan]: {type_str} (required)")
            else:
                default = param_info["default"]
                default_str = str(default) if default is not None else "None"
                panel_content.append(f"  [cyan]{name}[/cyan]: {type_str} = {default_str}")
    else:
        panel_content.append("[bold]Parameters:[/bold] None")
    
    # Add return type
    panel_content.append("")
    return_type = info["return_type"]
    if hasattr(return_type, "__name__"):
        return_str = return_type.__name__
    else:
        return_str = str(return_type).replace("typing.", "")
    panel_content.append(f"[bold]Returns:[/bold] {return_str}")
    
    # Display the panel
    console.print(Panel(
        "\n".join(panel_content),
        title=f"{method_info['component'].capitalize()} {method_info['name']}",
        border_style="green",
        expand=False
    ))
    
    # Show example usage
    console.print("\n[bold]Example Usage:[/bold]")
    command_name = method_path.replace(".", "-")
    example = f"python -m pytest_insight.utils.dev_cli {command_name}"
    
    # Add common options
    example += " --profile default"
    
    # Add method-specific parameters
    for name, param_info in info["params"].items():
        if not param_info["required"]:
            continue
        
        param_type = param_info["type"]
        if isinstance(param_type, type) and param_type is int:
            example += f" --{name.replace('_', '-')} 10"
        elif isinstance(param_type, type) and param_type is str:
            example += f" --{name.replace('_', '-')} value"
        elif isinstance(param_type, type) and param_type is bool:
            example += f" --{name.replace('_', '-')}"
    
    console.print(f"  {example}")


# Create dynamic commands for all API methods
api_methods = _discover_api_methods()
for method_key, method_info in api_methods.items():
    command_func = _create_dynamic_command(method_info)
    # Use a more readable command name format
    command_name = method_key.replace(".", "-")
    app.command(name=command_name)(command_func)


if __name__ == "__main__":
    app()
