"""Developer CLI functionality for pytest-insight."""

import inspect
import os
import traceback
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pytest_insight.core.analysis import Analysis
from pytest_insight.core.comparison import Comparison
from pytest_insight.core.core_api import InsightAPI
from pytest_insight.core.insights import Insights
from pytest_insight.core.query import Query
from pytest_insight.core.storage import get_active_profile, get_profile_manager

# Create CLI app
app = typer.Typer(
    help="Developer tools for exploring the pytest-insight API",
    context_settings={"help_option_names": ["--help", "-h"]},
)


class OutputFormat(str, Enum):
    """Output format for developer commands."""

    TEXT = "text"
    JSON = "json"


# API classes to expose
API_CLASSES = {
    "query": Query,
    "analysis": Analysis,
    "comparison": Comparison,
    "insights": Insights,
}


def _discover_api_methods() -> Dict[str, Dict[str, Any]]:
    """Discover all available API methods."""
    api_methods = {}

    for class_name, cls in API_CLASSES.items():
        methods = {}

        for name, member in inspect.getmembers(cls):
            # Skip private methods and special methods
            if name.startswith("_"):
                continue

            # Only include methods
            if inspect.isfunction(member) or inspect.ismethod(member):
                signature = inspect.signature(member)
                methods[name] = {
                    "signature": str(signature),
                    "doc": inspect.getdoc(member) or "No documentation available",
                    "parameters": [
                        {
                            "name": param_name,
                            "default": (
                                param.default
                                if param.default is not inspect.Parameter.empty
                                else None
                            ),
                            "required": param.default is inspect.Parameter.empty
                            and param.kind != inspect.Parameter.VAR_POSITIONAL
                            and param.kind != inspect.Parameter.VAR_KEYWORD,
                            "kind": str(param.kind),
                        }
                        for param_name, param in signature.parameters.items()
                        if param_name != "self"
                    ],
                }

        api_methods[class_name] = methods

    return api_methods


def _format_rich_output(data: Any, title: str = None):
    """Format data for rich console output."""
    console = Console()

    if isinstance(data, dict):
        # Create a table for dict data
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")

        for key, value in data.items():
            if isinstance(value, dict):
                nested_value = _format_nested_dict(value)
                table.add_row(str(key), nested_value)
            elif isinstance(value, list):
                nested_value = _format_nested_list(value)
                table.add_row(str(key), nested_value)
            else:
                table.add_row(str(key), str(value))

        if title:
            console.print(Panel(table, title=title))
        else:
            console.print(table)

    elif isinstance(data, list):
        # Create a table for list data
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Index", style="cyan")
        table.add_column("Value", style="green")

        for i, item in enumerate(data):
            if isinstance(item, dict):
                nested_value = _format_nested_dict(item)
                table.add_row(str(i), nested_value)
            elif isinstance(item, list):
                nested_value = _format_nested_list(item)
                table.add_row(str(i), nested_value)
            else:
                table.add_row(str(i), str(item))

        if title:
            console.print(Panel(table, title=title))
        else:
            console.print(table)

    else:
        # Just print the data
        if title:
            console.print(Panel(str(data), title=title))
        else:
            console.print(data)


def _format_nested_dict(data: Dict) -> str:
    """Format a nested dictionary for display."""
    result = []
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            result.append(f"{key}: [...]")
        else:
            result.append(f"{key}: {value}")
    return "\n".join(result)


def _format_nested_list(data: List) -> str:
    """Format a nested list for display."""
    if not data:
        return "[]"

    if len(data) > 3:
        sample = data[:3]
        result = [str(item) for item in sample]
        return f"[{', '.join(result)}, ... ({len(data)} items)]"
    else:
        result = [str(item) for item in data]
        return f"[{', '.join(result)}]"


def _execute_query_method(method_name: str, **kwargs):
    """Execute a Query method with the given arguments."""
    try:
        query = Query()
        method = getattr(query, method_name)
        result = method(**kwargs)
        return result
    except Exception as e:
        console = Console()
        console.print(f"Error executing Query.{method_name}: {str(e)}", style="red")
        console.print(traceback.format_exc(), style="red")
        return None


def _execute_stub_method(class_name: str, method_name: str, **kwargs):
    """Execute a stub method for non-Query classes."""
    console = Console()
    console.print(
        f"Called {class_name.capitalize()}.{method_name} with arguments:",
        style="yellow",
    )

    if kwargs:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="green")

        for key, value in kwargs.items():
            table.add_row(key, str(value))

        console.print(table)
    else:
        console.print("No arguments provided", style="yellow")

    console.print(
        "[yellow]This method is currently stubbed and not fully implemented.[/yellow]"
    )
    return None


def _create_method_command(
    class_name: str, method_name: str, method_info: Dict[str, Any]
) -> Callable:
    """Create a command function for a specific API method."""

    def command_function(**kwargs):
        """Dynamic command function for API methods."""
        console = Console()
        console.print(
            f"Executing {class_name.capitalize()}.{method_name}...", style="blue"
        )

        # Execute the appropriate method
        if class_name == "query":
            result = _execute_query_method(method_name, **kwargs)
        else:
            result = _execute_stub_method(class_name, method_name, **kwargs)

        if result is not None:
            _format_rich_output(
                result, title=f"Result of {class_name.capitalize()}.{method_name}"
            )

    # Update function metadata
    command_function.__name__ = f"{class_name}_{method_name}"
    command_function.__doc__ = method_info["doc"]

    return command_function


def _register_api_commands():
    """Register commands for all API methods."""
    api_methods = _discover_api_methods()

    for class_name, methods in api_methods.items():
        # Create a subcommand group for each class
        class_app = typer.Typer(
            help=f"{class_name.capitalize()} API commands",
            context_settings={"help_option_names": ["--help", "-h"]},
        )

        for method_name, method_info in methods.items():
            # Create a command function for this method
            command_func = _create_method_command(class_name, method_name, method_info)

            # Add parameters to the command
            for param in method_info["parameters"]:
                param_name = param["name"]
                required = param["required"]
                default = param["default"]

                if required:
                    typer.Argument(..., help=f"Required parameter: {param_name}")
                else:
                    typer.Option(default, help=f"Optional parameter: {param_name}")

            # Register the command
            class_app.command(name=method_name)(command_func)

        # Add the class subcommand to the main app
        app.add_typer(class_app, name=class_name)


def _start_interactive_shell():
    """Start an interactive shell for exploring the API."""
    console = Console()
    console.print(
        "[bold green]Starting interactive pytest-insight shell...[/bold green]"
    )
    console.print("Type 'help' for a list of commands, 'exit' or 'quit' to exit.")

    # Import core API classes to make them available in this scope
    from pytest_insight.core.analysis import Analysis
    from pytest_insight.core.comparison import Comparison
    from pytest_insight.core.core_api import compare as core_compare
    from pytest_insight.core.core_api import query as core_query
    from pytest_insight.core.insights import Insights
    from pytest_insight.core.query import Query

    # Initialize context
    context = {
        "active_profile": get_active_profile().name,  # Use system's active profile
        "queries": {},  # Store queries by name
        "results": {},  # Store results by name
        "current_query": None,
        "current_result": None,
        "in_test_filter": False,  # Flag to track if we're in a test filter context
        "test_filter_builder": None,  # Store the TestFilterBuilder
        "history": [],  # Store command history with results
        "debug_mode": False,  # Flag to enable/disable debug mode
        # Make core classes available to the shell
        "Query": Query,
        "Analysis": Analysis,
        "Comparison": Comparison,
        "Insights": Insights,
        "InsightAPI": InsightAPI,
        # Make core API functions available
        "query": core_query,
        "compare": core_compare,
        "analyze": core_analyze,
        "get_insights": core_get_insights,
    }

    # Define available commands and completions
    commands = [
        "help",
        "exit",
        "quit",
        "history",
        "clear",
        "debug on",
        "debug off",
        "debug status",
        "profile list",
        "profile create",
        "profile switch",
        "profile active",
        "python",
        "api help",
        "api query",
        "api compare",
        "api analyze",
        "api insights",
        "api exec",
        "query new",
        "query list",
        "query show",
        "query save",
        "query load",
        "query execute",
        "query filter_by_test",
        "query test_filter",
        "query apply_test_filter",
        "query filter",
        "query test",
        "query chain",
        "result list",
        "result show",
        "result save",
        "result compare",
        "session list",
        "session show",
        "session tests",
        "session failures",
    ]

    # Create prompt session with history and auto-completion
    try:
        from pathlib import Path

        # Create history directory if it doesn't exist
        history_dir = Path.home() / ".pytest_insight"
        history_dir.mkdir(exist_ok=True)
        history_file = history_dir / "shell_history"

        history = FileHistory(str(history_file))
    except Exception:
        # Fall back to in-memory history if file history fails
        history = InMemoryHistory()

    completer = WordCompleter(commands, ignore_case=True)

    style = Style.from_dict(
        {
            "prompt": "ansicyan bold",
        }
    )

    prompt_session = PromptSession(history=history, completer=completer, style=style)

    # Main loop
    while True:
        try:
            # Get user input with current profile in prompt
            user_input = prompt_session.prompt(
                f"\n[pytest-insight:{context['active_profile']}] > "
            )

            # Skip empty input
            if not user_input.strip():
                continue

            # Add to history
            context["history"].append({"command": user_input, "result": None})
            history_index = len(context["history"]) - 1

            # Exit command
            if user_input.lower() in ["exit", "quit"]:
                break

            # Help command
            if user_input.lower() == "help":
                console.print("\n[bold]Available commands:[/bold]")
                console.print("  [bold cyan]General:[/bold cyan]")
                console.print("    help                  - Show this help message")
                console.print("    exit, quit            - Exit the shell")
                console.print("    history               - Show command history")
                console.print("    clear                 - Clear the screen")
                console.print(
                    "    debug on/off/status   - Enable/disable/check debug mode"
                )
                console.print(
                    "    python EXPRESSION     - Execute a Python expression in the shell context"
                )

                console.print("\n  [bold cyan]Core API Access:[/bold cyan]")
                console.print(
                    "    api help              - Show help for working with core API classes directly"
                )
                console.print(
                    "    api query             - Create a new Query instance using the core API"
                )
                console.print(
                    "    api compare           - Create a new Comparison instance using the core API"
                )
                console.print(
                    "    api analyze           - Create a new Analysis instance using the core API"
                )
                console.print(
                    "    api insights          - Create a new Insights instance using the core API"
                )
                console.print(
                    "    api exec              - Execute a method on a core API object"
                )

                console.print("\n  [bold cyan]Profile Management:[/bold cyan]")
                console.print("    profile list          - List all available profiles")
                console.print("    profile create NAME   - Create a new profile")
                console.print(
                    "    profile switch NAME   - Switch to a different profile"
                )
                console.print("    profile active        - Show the active profile")

                console.print("\n  [bold cyan]Query Management:[/bold cyan]")
                console.print("    query new             - Start a new query")
                console.print("    query list            - List saved queries")
                console.print("    query show NAME       - Show a saved query")
                console.print("    query save NAME       - Save the current query")
                console.print("    query load NAME       - Load a saved query")
                console.print("    query execute         - Execute the current query")
                console.print(
                    "    query filter_by_test  - Start building test-level filters"
                )
                console.print(
                    "    query test_filter TYPE VALUE - Add a test filter (when in test filter mode)"
                )
                console.print(
                    "    query apply_test_filter - Apply test filters and return to query context"
                )

                console.print("\n  [bold cyan]Filtering (Detailed):[/bold cyan]")
                console.print(
                    "    query filter_by_test  - Start building test-level filters"
                )
                console.print(
                    "    query test_filter TYPE VALUE - Add a test filter (when in test filter mode)"
                )
                console.print(
                    "    query apply_test_filter - Apply test filters and return to query context"
                )

                console.print("\n  [bold cyan]Filtering (Streamlined):[/bold cyan]")
                console.print(
                    "    query filter TYPE VALUE - Add a session-level filter (e.g., days, sut, outcome)"
                )
                console.print(
                    "    query test TYPE VALUE   - Add a test-level filter (automatically applies)"
                )
                console.print(
                    "    query chain FILTER1:VALUE1 FILTER2:VALUE2 ... - Create a complete query in one line"
                )
                console.print(
                    "      Example: query chain days:7 sut:myapp test:outcome:failed test:duration_gt:5"
                )

                console.print("\n  [bold cyan]Result Management:[/bold cyan]")
                console.print("    result list           - List saved results")
                console.print("    result show NAME      - Show a saved result")
                console.print("    result save NAME      - Save the current result")
                console.print("    result compare NAME1 NAME2 - Compare two results")

                console.print("\n  [bold cyan]Session Management:[/bold cyan]")
                console.print(
                    "    session list          - List sessions in current result"
                )
                console.print("    session show ID       - Show details of a session")
                console.print("    session tests ID      - List tests in a session")
                console.print(
                    "    session failures ID   - List failed tests in a session"
                )
                continue

            # History command
            if user_input.lower() == "history":
                table = Table(title="Command History")
                table.add_column("#")
                table.add_column("Command")
                table.add_column("Result")

                for i, item in enumerate(
                    context["history"][:-1]
                ):  # Skip current command
                    result_summary = "N/A"
                    if item["result"]:
                        if (
                            isinstance(item["result"], dict)
                            and "summary" in item["result"]
                        ):
                            result_summary = item["result"]["summary"]
                        else:
                            result_summary = (
                                str(item["result"])[:50] + "..."
                                if len(str(item["result"])) > 50
                                else str(item["result"])
                            )

                    table.add_row(str(i), item["command"], result_summary)

                console.print(table)
                context["history"][history_index]["result"] = {
                    "summary": "Showed command history"
                }
                continue

            # Clear command
            if user_input.lower() == "clear":
                console.clear()
                context["history"][history_index]["result"] = {
                    "action": "cleared screen"
                }
                continue

            # Debug command
            elif user_input.lower().startswith("debug"):
                parts = user_input.lower().split()
                if len(parts) < 2:
                    console.print(
                        "[bold red]Error:[/bold red] Debug command requires an argument (on, off, or status)"
                    )
                    context["history"][history_index]["result"] = {
                        "error": "Missing debug argument"
                    }
                    continue

                debug_action = parts[1]
                if debug_action == "on":
                    context["debug_mode"] = True
                    console.print("[bold green]Debug mode enabled[/bold green]")
                    context["history"][history_index]["result"] = {
                        "action": "debug mode enabled"
                    }
                elif debug_action == "off":
                    context["debug_mode"] = False
                    console.print("[bold yellow]Debug mode disabled[/bold yellow]")
                    context["history"][history_index]["result"] = {
                        "action": "debug mode disabled"
                    }
                elif debug_action == "status":
                    status = "enabled" if context["debug_mode"] else "disabled"
                    console.print(
                        f"[bold blue]Debug mode is currently {status}[/bold blue]"
                    )
                    context["history"][history_index]["result"] = {
                        "status": f"debug mode {status}"
                    }
                else:
                    console.print(
                        "[bold red]Error:[/bold red] Invalid debug argument. Use 'on', 'off', or 'status'"
                    )
                    context["history"][history_index]["result"] = {
                        "error": "Invalid debug argument"
                    }
                continue

            # Query chain command - show current query chain
            elif (
                user_input.lower() == "query chain"
                or user_input.lower() == "query.chain"
            ):
                if context["current_query"] is None:
                    console.print("[bold red]Error:[/bold red] No active query")
                    context["history"][history_index]["result"] = {
                        "error": "No active query"
                    }
                    continue

                # Get the chain of methods that have been called
                chain = []
                query_obj = context["current_query"]

                # This is a simplified representation as we can't easily extract the actual chain
                chain_str = "Query()"

                if hasattr(query_obj, "_profile_name") and query_obj._profile_name:
                    chain_str += f".with_profile('{query_obj._profile_name}')"
                    chain.append(f"with_profile('{query_obj._profile_name}')")

                if hasattr(query_obj, "_filters") and query_obj._filters:
                    for filter_type, filter_value in query_obj._filters.items():
                        if filter_type == "days":
                            chain_str += f".in_last_days({filter_value})"
                            chain.append(f"in_last_days({filter_value})")
                        elif filter_type == "hours":
                            chain_str += f".in_last_hours({filter_value})"
                            chain.append(f"in_last_hours({filter_value})")
                        elif filter_type == "minutes":
                            chain_str += f".in_last_minutes({filter_value})"
                            chain.append(f"in_last_minutes({filter_value})")
                        elif filter_type == "sut":
                            chain_str += f".for_sut('{filter_value}')"
                            chain.append(f"for_sut('{filter_value}')")
                        elif filter_type == "session_tag":
                            chain_str += f".with_session_tag('{filter_value}')"
                            chain.append(f"with_session_tag('{filter_value}')")
                        elif filter_type == "session_id_pattern":
                            chain_str += f".with_session_id_pattern('{filter_value}')"
                            chain.append(f"with_session_id_pattern('{filter_value}')")

                console.print("[bold]Current Query Chain:[/bold]")
                console.print(chain_str)

                # Show more detailed information in debug mode
                if context["debug_mode"]:
                    console.print(
                        "\n[bold blue]DEBUG: Query Object Details:[/bold blue]"
                    )

                    # Show all attributes of the query object
                    for attr_name in dir(query_obj):
                        # Skip private attributes and methods
                        if (
                            attr_name.startswith("_")
                            and attr_name != "_profile_name"
                            and attr_name != "_filters"
                        ):
                            continue

                        # Skip methods
                        attr = getattr(query_obj, attr_name)
                        if callable(attr):
                            continue

                        # Display the attribute
                        console.print(f"[blue]{attr_name}: {repr(attr)}[/blue]")

                    # Show equivalent Python code
                    console.print(
                        "\n[bold blue]DEBUG: Equivalent Python Code:[/bold blue]"
                    )
                    console.print(
                        "[blue]from pytest_insight.core.query import Query[/blue]"
                    )
                    console.print(f"[blue]query = {chain_str}[/blue]")
                    console.print("[blue]result = query.execute()[/blue]")

                context["history"][history_index]["result"] = {"query_chain": chain}
                continue

            # Handle dot notation for query methods (e.g., query.with_profile default)
            elif user_input.lower().startswith("query."):
                parts = user_input.lower().split(".", 1)
                if len(parts) < 2:
                    console.print(
                        "[bold red]Error:[/bold red] Invalid query command format"
                    )
                    context["history"][history_index]["result"] = {
                        "error": "Invalid query command format"
                    }
                    continue

                # Extract method name and arguments
                method_parts = parts[1].split(" ", 1)
                method_name = method_parts[0].strip()

                # Extract arguments if any
                args = []
                if len(method_parts) > 1:
                    arg_str = method_parts[1].strip()
                    if arg_str:
                        # Simple argument parsing - split by spaces for positional args
                        raw_args = [arg.strip() for arg in arg_str.split()]

                        # Convert arguments to appropriate types
                        for arg in raw_args:
                            # Try to convert to appropriate type
                            try:
                                if arg.lower() == "true":
                                    args.append(True)
                                elif arg.lower() == "false":
                                    args.append(False)
                                elif arg.isdigit():
                                    args.append(int(arg))
                                elif arg.replace(".", "", 1).isdigit():
                                    args.append(float(arg))
                                else:
                                    args.append(arg)
                            except Exception:
                                args.append(arg)

                # Initialize query if needed
                if context["current_query"] is None:
                    context["current_query"] = Query()

                # Show debug information if debug mode is enabled
                if context["debug_mode"]:
                    console.print(
                        "[bold blue]DEBUG: Executing Python API call:[/bold blue]"
                    )
                    arg_display = ", ".join([repr(a) for a in args])
                    api_call = f"Query.{method_name}({arg_display})"
                    console.print(f"[blue]{api_call}[/blue]")

                # Get the method from the Query class
                if method_name == "chain":
                    # Special handling for chain command
                    if context["current_query"] is None:
                        console.print("[bold red]Error:[/bold red] No active query")
                        context["history"][history_index]["result"] = {
                            "error": "No active query"
                        }
                        continue

                    # Get the chain of methods that have been called
                    chain = []
                    query_obj = context["current_query"]

                    # This is a simplified representation as we can't easily extract the actual chain
                    chain_str = "Query()"

                    if hasattr(query_obj, "_profile_name") and query_obj._profile_name:
                        chain_str += f".with_profile('{query_obj._profile_name}')"
                        chain.append(f"with_profile('{query_obj._profile_name}')")

                    if hasattr(query_obj, "_filters") and query_obj._filters:
                        for filter_type, filter_value in query_obj._filters.items():
                            if filter_type == "days":
                                chain_str += f".in_last_days({filter_value})"
                                chain.append(f"in_last_days({filter_value})")
                            elif filter_type == "hours":
                                chain_str += f".in_last_hours({filter_value})"
                                chain.append(f"in_last_hours({filter_value})")
                            elif filter_type == "minutes":
                                chain_str += f".in_last_minutes({filter_value})"
                                chain.append(f"in_last_minutes({filter_value})")
                            elif filter_type == "sut":
                                chain_str += f".for_sut('{filter_value}')"
                                chain.append(f"for_sut('{filter_value}')")
                            elif filter_type == "session_tag":
                                chain_str += f".with_session_tag('{filter_value}')"
                                chain.append(f"with_session_tag('{filter_value}')")
                            elif filter_type == "session_id_pattern":
                                chain_str += (
                                    f".with_session_id_pattern('{filter_value}')"
                                )
                                chain.append(
                                    f"with_session_id_pattern('{filter_value}')"
                                )

                    console.print("[bold]Current Query Chain:[/bold]")
                    console.print(chain_str)

                    # Show more detailed information in debug mode
                    if context["debug_mode"]:
                        console.print(
                            "\n[bold blue]DEBUG: Query Object Details:[/bold blue]"
                        )

                        # Show all attributes of the query object
                        for attr_name in dir(query_obj):
                            # Skip private attributes and methods
                            if (
                                attr_name.startswith("_")
                                and attr_name != "_profile_name"
                                and attr_name != "_filters"
                            ):
                                continue

                            # Skip methods
                            attr = getattr(query_obj, attr_name)
                            if callable(attr):
                                continue

                            # Display the attribute
                            console.print(f"[blue]{attr_name}: {repr(attr)}[/blue]")

                        # Show equivalent Python code
                        console.print(
                            "\n[bold blue]DEBUG: Equivalent Python Code:[/bold blue]"
                        )
                        console.print(
                            "[blue]from pytest_insight.core.query import Query[/blue]"
                        )
                        console.print(f"[blue]query = {chain_str}[/blue]")
                        console.print("[blue]result = query.execute()[/blue]")

                    context["history"][history_index]["result"] = {"query_chain": chain}
                    continue
                elif hasattr(Query, method_name):
                    method = getattr(Query, method_name)

                    try:
                        # Execute the method
                        if method_name == "execute":
                            # Special handling for execute to store the result
                            result = method(context["current_query"], *args)
                            context["current_result"] = result

                            # Display result summary
                            session_count = (
                                len(result.sessions)
                                if hasattr(result, "sessions")
                                else 0
                            )
                            console.print(
                                "[bold green]Query executed successfully.[/bold green]"
                            )
                            console.print(f"Found {session_count} sessions.")

                            # Create a table to display the sessions
                            table = Table(title="Query Results")
                            table.add_column("Session ID")
                            table.add_column("SUT")
                            table.add_column("Start Time")
                            table.add_column("Duration (s)")
                            table.add_column("Tests")

                            for session in result.sessions[
                                :10
                            ]:  # Limit to 10 sessions for display
                                table.add_row(
                                    session.session_id,
                                    session.sut_name,
                                    str(session.session_start_time),
                                    str(round(session.session_duration, 2)),
                                    str(len(session.test_results)),
                                )

                            console.print(table)

                            if len(result.sessions) > 10:
                                console.print(
                                    f"Showing 10 of {len(result.sessions)} sessions."
                                )
                        else:
                            # For other methods, update the query object
                            result = method(context["current_query"], *args)

                            # If the method returns a new Query object, update current_query
                            if isinstance(result, Query):
                                context["current_query"] = result
                                console.print(
                                    f"[bold green]Applied {method_name}[/bold green]"
                                )
                            else:
                                console.print(
                                    f"[bold yellow]Warning: {method_name} did not return a Query object[/bold yellow]"
                                )

                            context["history"][history_index]["result"] = {
                                "action": f"applied {method_name}",
                                "args": args,
                            }
                    except Exception as e:
                        console.print(
                            f"[bold red]Error executing {method_name}:[/bold red] {str(e)}"
                        )
                        console.print(traceback.format_exc(), style="red")
                        context["history"][history_index]["result"] = {"error": str(e)}
                else:
                    console.print(
                        f"[bold red]Error:[/bold red] Unknown query method: {method_name}"
                    )
                    context["history"][history_index]["result"] = {
                        "error": f"Unknown query method: {method_name}"
                    }

                continue

            # Parse command
            parts = user_input.split()
            if not parts:
                continue

            command = parts[0].lower()

            # Profile management commands
            if command == "profile":
                if len(parts) < 2:
                    console.print(
                        "[bold red]Error:[/bold red] Missing profile subcommand"
                    )
                    context["history"][history_index]["result"] = {
                        "error": "Missing profile subcommand"
                    }
                    continue

                subcommand = parts[1].lower()

                if subcommand == "list":
                    # List all profiles
                    profile_manager = get_profile_manager()
                    profiles = profile_manager.list_profiles()
                    active_profile = context["active_profile"]

                    table = Table(title="Storage Profiles")
                    table.add_column("Profile Name")
                    table.add_column("Path")
                    table.add_column("Size")
                    table.add_column("Active")

                    def format_file_size(size_bytes):
                        """Format bytes to human readable size."""
                        if size_bytes == 0:
                            return "0 B"
                        size_names = ("B", "KB", "MB", "GB", "TB")
                        i = 0
                        while size_bytes >= 1024 and i < len(size_names) - 1:
                            size_bytes /= 1024
                            i += 1
                        return f"{size_bytes:.2f} {size_names[i]}"

                    for name, profile in profiles.items():
                        is_active = "✓" if name == active_profile else ""
                        file_path = profile.file_path

                        # Get file size if file exists
                        file_size = ""
                        if file_path and os.path.exists(file_path):
                            size_bytes = os.path.getsize(file_path)
                            file_size = format_file_size(size_bytes)
                        else:
                            file_size = "Not found"

                        table.add_row(name, file_path, file_size, is_active)

                    console.print(table)
                    context["history"][history_index]["result"] = {
                        "summary": f"Listed {len(profiles)} profiles"
                    }
                elif subcommand == "create":
                    if len(parts) < 3:
                        console.print(
                            "[bold red]Error:[/bold red] Missing profile name"
                        )
                        context["history"][history_index]["result"] = {
                            "error": "Missing profile name"
                        }
                        continue

                    name = parts[2]
                    console.print(f"Created profile [bold]{name}[/bold]")
                    context["history"][history_index]["result"] = {
                        "summary": f"Created profile {name}"
                    }

                elif subcommand == "switch":
                    if len(parts) < 3:
                        console.print(
                            "[bold red]Error:[/bold red] Missing profile name"
                        )
                        context["history"][history_index]["result"] = {
                            "error": "Missing profile name"
                        }
                        continue

                    name = parts[2]
                    context["active_profile"] = name
                    console.print(f"Switched to profile [bold]{name}[/bold]")
                    context["history"][history_index]["result"] = {
                        "summary": f"Switched to profile {name}"
                    }

                elif subcommand == "active":
                    console.print(
                        f"Active profile: [bold]{context['active_profile']}[/bold]"
                    )
                    context["history"][history_index]["result"] = {
                        "summary": f"Active profile: {context['active_profile']}"
                    }

                else:
                    console.print(
                        f"[bold red]Error:[/bold red] Unknown profile subcommand: {subcommand}"
                    )
                    context["history"][history_index]["result"] = {
                        "error": f"Unknown profile subcommand: {subcommand}"
                    }

            # Query commands
            elif command == "query":
                if len(parts) < 2:
                    console.print(
                        "[bold red]Error:[/bold red] Missing query subcommand"
                    )
                    context["history"][history_index]["result"] = {
                        "error": "Missing query subcommand"
                    }
                    continue

                subcommand = parts[1].lower()

                if subcommand == "new":
                    context["current_query"] = Query()
                    console.print("Created a new query")
                    context["history"][history_index]["result"] = {
                        "summary": "Created new query"
                    }

                elif subcommand == "list":
                    if not context["queries"]:
                        console.print("No saved queries")
                        context["history"][history_index]["result"] = {
                            "summary": "No saved queries"
                        }
                        continue

                    table = Table(title="Saved Queries")
                    table.add_column("Name")
                    table.add_column("Filters")

                    for name, query in context["queries"].items():
                        filters = str(query.to_dict().get("filters", {}))
                        table.add_row(name, filters)

                    console.print(table)
                    context["history"][history_index]["result"] = {
                        "summary": f"Listed {len(context['queries'])} queries"
                    }

                elif subcommand == "show":
                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing query name")
                        context["history"][history_index]["result"] = {
                            "error": "Missing query name"
                        }
                        continue

                    name = parts[2]
                    if name not in context["queries"]:
                        console.print(
                            f"[bold red]Error:[/bold red] Query '{name}' not found"
                        )
                        context["history"][history_index]["result"] = {
                            "error": f"Query '{name}' not found"
                        }
                        continue

                    query = context["queries"][name]
                    console.print(f"Query: [bold]{name}[/bold]")
                    console.print(f"Filters: {query.to_dict().get('filters', {})}")
                    context["history"][history_index]["result"] = {
                        "summary": f"Showed query {name}",
                        "query": query.to_dict(),
                    }

                elif subcommand == "save":
                    if not context["current_query"]:
                        console.print(
                            "[bold red]Error:[/bold red] No active query to save"
                        )
                        context["history"][history_index]["result"] = {
                            "error": "No active query to save"
                        }
                        continue

                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing query name")
                        context["history"][history_index]["result"] = {
                            "error": "Missing query name"
                        }
                        continue

                    name = parts[2]
                    context["queries"][name] = context["current_query"]
                    console.print(f"Saved query as [bold]{name}[/bold]")
                    context["history"][history_index]["result"] = {
                        "summary": f"Saved query as {name}"
                    }

                elif subcommand == "load":
                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing query name")
                        context["history"][history_index]["result"] = {
                            "error": "Missing query name"
                        }
                        continue

                    name = parts[2]
                    if name not in context["queries"]:
                        console.print(
                            f"[bold red]Error:[/bold red] Query '{name}' not found"
                        )
                        context["history"][history_index]["result"] = {
                            "error": f"Query '{name}' not found"
                        }
                        continue

                    context["current_query"] = context["queries"][name]
                    console.print(f"Loaded query [bold]{name}[/bold]")
                    context["history"][history_index]["result"] = {
                        "summary": f"Loaded query {name}"
                    }

                elif subcommand == "execute":
                    if not context["current_query"]:
                        console.print(
                            "[bold red]Error:[/bold red] No active query to execute"
                        )
                        context["history"][history_index]["result"] = {
                            "error": "No active query to execute"
                        }
                        continue

                    try:
                        result = context["current_query"].execute()
                        context["current_result"] = result

                        console.print(
                            f"Query executed successfully. Found {len(result.sessions)} sessions."
                        )
                        context["history"][history_index]["result"] = {
                            "summary": f"Query executed, found {len(result.sessions)} sessions",
                            "session_count": len(result.sessions),
                        }

                        if result.sessions:
                            table = Table(title="Query Results")
                            table.add_column("Session ID")
                            table.add_column("SUT")
                            table.add_column("Start Time")
                            table.add_column("Duration (s)")
                            table.add_column("Tests")

                            for session in result.sessions[
                                :10
                            ]:  # Limit to 10 sessions for display
                                table.add_row(
                                    session.session_id,
                                    session.sut_name,
                                    str(session.session_start_time),
                                    str(round(session.session_duration, 2)),
                                    str(len(session.test_results)),
                                )

                            console.print(table)

                            if len(result.sessions) > 10:
                                console.print(
                                    f"Showing 10 of {len(result.sessions)} sessions."
                                )
                    except Exception as e:
                        console.print(f"[bold red]Error:[/bold red] {str(e)}")
                        console.print(traceback.format_exc(), style="red")
                        context["history"][history_index]["result"] = {"error": str(e)}

                elif subcommand == "filter_by_test":
                    if not context["current_query"]:
                        console.print(
                            "[bold red]Error:[/bold red] No active query. Use 'query new' first."
                        )
                        context["history"][history_index]["result"] = {
                            "error": "No active query to filter"
                        }
                        continue

                    # Enter test filter mode
                    context["in_test_filter"] = True
                    context["test_filter_builder"] = context[
                        "current_query"
                    ].filter_by_test()
                    console.print(
                        "[bold green]Entered test filter mode.[/bold green] Use 'query test_filter TYPE VALUE' to add filters and 'query apply_test_filter' when done."
                    )
                    context["history"][history_index]["result"] = {
                        "summary": "Entered test filter mode"
                    }

                elif subcommand == "test_filter":
                    if (
                        not context["in_test_filter"]
                        or not context["test_filter_builder"]
                    ):
                        console.print(
                            "[bold red]Error:[/bold red] Not in test filter mode. Use 'query filter_by_test' first."
                        )
                        context["history"][history_index]["result"] = {
                            "error": "Not in test filter mode"
                        }
                        continue

                    if len(parts) < 4:
                        console.print(
                            "[bold red]Error:[/bold red] Missing filter type or value"
                        )
                        context["history"][history_index]["result"] = {
                            "error": "Missing filter type or value"
                        }
                        continue

                    filter_type = parts[2].lower()
                    filter_value = " ".join(parts[3:])

                    try:
                        builder = context["test_filter_builder"]

                        if filter_type == "outcome":
                            builder = builder.with_outcome(filter_value)
                        elif filter_type == "duration_gt":
                            builder = builder.with_duration_greater_than(
                                float(filter_value)
                            )
                        elif filter_type == "duration_lt":
                            builder = builder.with_duration_less_than(
                                float(filter_value)
                            )
                        elif filter_type == "nodeid":
                            builder = builder.with_nodeid_pattern(filter_value)
                        elif filter_type == "name":
                            builder = builder.with_name_pattern(filter_value)
                        else:
                            console.print(
                                f"[bold red]Error:[/bold red] Unknown test filter type: {filter_type}"
                            )
                            context["history"][history_index]["result"] = {
                                "error": f"Unknown test filter type: {filter_type}"
                            }
                            continue

                        context["test_filter_builder"] = builder
                        console.print(
                            f"Added test filter: {filter_type} = {filter_value}"
                        )
                        context["history"][history_index]["result"] = {
                            "summary": f"Added test filter: {filter_type} = {filter_value}"
                        }
                    except Exception as e:
                        console.print(f"[bold red]Error:[/bold red] {str(e)}")
                        console.print(traceback.format_exc(), style="red")
                        context["history"][history_index]["result"] = {"error": str(e)}

                elif subcommand == "apply_test_filter":
                    if (
                        not context["in_test_filter"]
                        or not context["test_filter_builder"]
                    ):
                        console.print(
                            "[bold red]Error:[/bold red] Not in test filter mode. Use 'query filter_by_test' first."
                        )
                        context["history"][history_index]["result"] = {
                            "error": "Not in test filter mode"
                        }
                        continue

                    try:
                        # Apply the test filters and return to query context
                        context["current_query"] = context[
                            "test_filter_builder"
                        ].apply()
                        context["in_test_filter"] = False
                        context["test_filter_builder"] = None
                        console.print(
                            "[bold green]Applied test filters.[/bold green] Returned to query context."
                        )
                        context["history"][history_index]["result"] = {
                            "summary": "Applied test filters"
                        }
                    except Exception as e:
                        console.print(f"[bold red]Error:[/bold red] {str(e)}")
                        console.print(traceback.format_exc(), style="red")
                        context["history"][history_index]["result"] = {"error": str(e)}

                elif subcommand == "filter":
                    if not context["current_query"]:
                        console.print(
                            "[bold red]Error:[/bold red] No active query. Use 'query new' first."
                        )
                        context["history"][history_index]["result"] = {
                            "error": "No active query to filter"
                        }
                        continue

                    if len(parts) < 4:
                        console.print(
                            "[bold red]Error:[/bold red] Missing filter type or value"
                        )
                        context["history"][history_index]["result"] = {
                            "error": "Missing filter type or value"
                        }
                        continue

                    filter_type = parts[2].lower()
                    filter_value = " ".join(parts[3:])

                    try:
                        query = context["current_query"]

                        if filter_type == "days":
                            query = query.in_last_days(int(filter_value))
                        elif filter_type == "hours":
                            query = query.in_last_hours(int(filter_value))
                        elif filter_type == "sut":
                            query = query.for_sut(filter_value)
                        elif filter_type == "outcome":
                            query = query.with_outcome(filter_value)
                        elif filter_type == "branch":
                            query = query.for_branch(filter_value)
                        elif filter_type == "commit":
                            query = query.for_commit(filter_value)
                        elif filter_type == "nodeid":
                            query = query.test_nodeid_contains(filter_value)
                        else:
                            console.print(
                                f"[bold red]Error:[/bold red] Unknown filter type: {filter_type}"
                            )
                            context["history"][history_index]["result"] = {
                                "error": f"Unknown filter type: {filter_type}"
                            }
                            continue

                        context["current_query"] = query
                        console.print(f"Added filter: {filter_type} = {filter_value}")
                        context["history"][history_index]["result"] = {
                            "summary": f"Added filter: {filter_type} = {filter_value}"
                        }
                    except Exception as e:
                        console.print(f"[bold red]Error:[/bold red] {str(e)}")
                        console.print(traceback.format_exc(), style="red")
                        context["history"][history_index]["result"] = {"error": str(e)}

                elif subcommand == "test":
                    if not context["current_query"]:
                        console.print(
                            "[bold red]Error:[/bold red] No active query. Use 'query new' first."
                        )
                        context["history"][history_index]["result"] = {
                            "error": "No active query to filter"
                        }
                        continue

                    if len(parts) < 4:
                        console.print(
                            "[bold red]Error:[/bold red] Missing filter type or value"
                        )
                        context["history"][history_index]["result"] = {
                            "error": "Missing filter type or value"
                        }
                        continue

                    filter_type = parts[2].lower()
                    filter_value = " ".join(parts[3:])

                    try:
                        # Create a test filter builder if not already in test mode
                        if not context["in_test_filter"]:
                            context["in_test_filter"] = True
                            context["test_filter_builder"] = context[
                                "current_query"
                            ].filter_by_test()

                        builder = context["test_filter_builder"]

                        if filter_type == "outcome":
                            builder = builder.with_outcome(filter_value)
                        elif filter_type == "duration_gt":
                            builder = builder.with_duration_greater_than(
                                float(filter_value)
                            )
                        elif filter_type == "duration_lt":
                            builder = builder.with_duration_less_than(
                                float(filter_value)
                            )
                        elif filter_type == "nodeid":
                            builder = builder.with_nodeid_pattern(filter_value)
                        elif filter_type == "name":
                            builder = builder.with_name_pattern(filter_value)
                        else:
                            console.print(
                                f"[bold red]Error:[/bold red] Unknown test filter type: {filter_type}"
                            )
                            context["history"][history_index]["result"] = {
                                "error": f"Unknown test filter type: {filter_type}"
                            }
                            continue

                        context["test_filter_builder"] = builder

                        # Automatically apply the test filter
                        context["current_query"] = builder.apply()
                        context["in_test_filter"] = False
                        context["test_filter_builder"] = None

                        console.print(
                            f"Added and applied test filter: {filter_type} = {filter_value}"
                        )
                        context["history"][history_index]["result"] = {
                            "summary": f"Added and applied test filter: {filter_type} = {filter_value}"
                        }
                    except Exception as e:
                        console.print(f"[bold red]Error:[/bold red] {str(e)}")
                        console.print(traceback.format_exc(), style="red")
                        context["history"][history_index]["result"] = {"error": str(e)}

                elif subcommand == "chain":
                    if len(parts) < 3:
                        console.print(
                            "[bold red]Error:[/bold red] Missing filter specifications"
                        )
                        context["history"][history_index]["result"] = {
                            "error": "Missing filter specifications"
                        }
                        continue

                    # Create a new query
                    query = Query()

                    # Track if we're in test filter mode
                    in_test_filter = False
                    test_filter_builder = None

                    # Process all filter specifications
                    filter_specs = parts[2:]
                    applied_filters = []

                    try:
                        for spec in filter_specs:
                            # Parse filter specification (type:value)
                            if ":" not in spec:
                                raise ValueError(
                                    f"Invalid filter specification: {spec}. Format should be type:value"
                                )

                            parts = spec.split(":", 1)
                            filter_type = parts[0].lower()
                            filter_value = parts[1]

                            # Check if this is a test filter
                            if filter_type.startswith("test:"):
                                # Extract the actual test filter type
                                test_filter_type = filter_type[5:]

                                # Create test filter builder if not already in test mode
                                if not in_test_filter:
                                    in_test_filter = True
                                    test_filter_builder = query.filter_by_test()

                                # Apply the test filter
                                if test_filter_type == "outcome":
                                    test_filter_builder = (
                                        test_filter_builder.with_outcome(filter_value)
                                    )
                                elif test_filter_type == "duration_gt":
                                    test_filter_builder = (
                                        test_filter_builder.with_duration_greater_than(
                                            float(filter_value)
                                        )
                                    )
                                elif test_filter_type == "duration_lt":
                                    test_filter_builder = (
                                        test_filter_builder.with_duration_less_than(
                                            float(filter_value)
                                        )
                                    )
                                elif test_filter_type == "nodeid":
                                    test_filter_builder = (
                                        test_filter_builder.with_nodeid_pattern(
                                            filter_value
                                        )
                                    )
                                elif test_filter_type == "name":
                                    test_filter_builder = (
                                        test_filter_builder.with_name_pattern(
                                            filter_value
                                        )
                                    )
                                else:
                                    raise ValueError(
                                        f"Unknown test filter type: {test_filter_type}"
                                    )

                                applied_filters.append(
                                    f"test:{test_filter_type}:{filter_value}"
                                )
                            else:
                                # If we were in test filter mode, apply those filters first
                                if in_test_filter:
                                    query = test_filter_builder.apply()
                                    in_test_filter = False
                                    test_filter_builder = None

                                # Apply session filter
                                if filter_type == "days":
                                    query = query.in_last_days(int(filter_value))
                                elif filter_type == "hours":
                                    query = query.in_last_hours(int(filter_value))
                                elif filter_type == "sut":
                                    query = query.for_sut(filter_value)
                                elif filter_type == "outcome":
                                    query = query.with_outcome(filter_value)
                                elif filter_type == "branch":
                                    query = query.for_branch(filter_value)
                                elif filter_type == "commit":
                                    query = query.for_commit(filter_value)
                                elif filter_type == "nodeid":
                                    query = query.test_nodeid_contains(filter_value)
                                else:
                                    raise ValueError(
                                        f"Unknown filter type: {filter_type}"
                                    )

                                applied_filters.append(f"{filter_type}:{filter_value}")

                        # If we're still in test filter mode, apply those filters
                        if in_test_filter:
                            query = test_filter_builder.apply()

                        # Store the query
                        context["current_query"] = query

                        # Show summary
                        console.print(
                            "[bold green]Created query with filters:[/bold green]"
                        )
                        for filter_spec in applied_filters:
                            console.print(f"  - {filter_spec}")

                        context["history"][history_index]["result"] = {
                            "summary": "Created query with filters",
                            "filters": applied_filters,
                        }
                    except Exception as e:
                        console.print(f"[bold red]Error:[/bold red] {str(e)}")
                        console.print(traceback.format_exc(), style="red")
                        context["history"][history_index]["result"] = {"error": str(e)}

            # Result commands
            elif command == "result":
                if len(parts) < 2:
                    console.print(
                        "[bold red]Error:[/bold red] Missing result subcommand"
                    )
                    context["history"][history_index]["result"] = {
                        "error": "Missing result subcommand"
                    }
                    continue

                subcommand = parts[1].lower()

                if subcommand == "list":
                    if not context["results"]:
                        console.print("No saved results")
                        context["history"][history_index]["result"] = {
                            "summary": "No saved results"
                        }
                        continue

                    table = Table(title="Saved Results")
                    table.add_column("Name")
                    table.add_column("Sessions")

                    for name, result in context["results"].items():
                        table.add_row(name, str(len(result.sessions)))

                    console.print(table)
                    context["history"][history_index]["result"] = {
                        "summary": f"Listed {len(context['results'])} results"
                    }

                elif subcommand == "show":
                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing result name")
                        context["history"][history_index]["result"] = {
                            "error": "Missing result name"
                        }
                        continue

                    name = parts[2]
                    if name not in context["results"]:
                        console.print(
                            f"[bold red]Error:[/bold red] Result '{name}' not found"
                        )
                        context["history"][history_index]["result"] = {
                            "error": f"Result '{name}' not found"
                        }
                        continue

                    result = context["results"][name]
                    console.print(f"Result: [bold]{name}[/bold]")
                    console.print(f"Sessions: {len(result.sessions)}")

                    if result.sessions:
                        table = Table(title=f"Result: {name}")
                        table.add_column("Session ID")
                        table.add_column("SUT")
                        table.add_column("Start Time")
                        table.add_column("Duration (s)")
                        table.add_column("Tests")

                        for session in result.sessions[
                            :10
                        ]:  # Limit to 10 sessions for display
                            table.add_row(
                                session.session_id,
                                session.sut_name,
                                str(session.session_start_time),
                                str(round(session.session_duration, 2)),
                                str(len(session.test_results)),
                            )

                        console.print(table)

                        if len(result.sessions) > 10:
                            console.print(
                                f"Showing 10 of {len(result.sessions)} sessions."
                            )

                    context["history"][history_index]["result"] = {
                        "summary": f"Showed result {name}"
                    }

                elif subcommand == "save":
                    if not context["current_result"]:
                        console.print(
                            "[bold red]Error:[/bold red] No active result to save"
                        )
                        context["history"][history_index]["result"] = {
                            "error": "No active result to save"
                        }
                        continue

                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing result name")
                        context["history"][history_index]["result"] = {
                            "error": "Missing result name"
                        }
                        continue

                    name = parts[2]
                    context["results"][name] = context["current_result"]
                    console.print(f"Saved result as [bold]{name}[/bold]")
                    context["history"][history_index]["result"] = {
                        "summary": f"Saved result as {name}"
                    }

                elif subcommand == "compare":
                    if len(parts) < 4:
                        console.print(
                            "[bold red]Error:[/bold red] Missing result names to compare"
                        )
                        context["history"][history_index]["result"] = {
                            "error": "Missing result names to compare"
                        }
                        continue

                    name1 = parts[2]
                    name2 = parts[3]

                    if name1 not in context["results"]:
                        console.print(
                            f"[bold red]Error:[/bold red] Result '{name1}' not found"
                        )
                        context["history"][history_index]["result"] = {
                            "error": f"Result '{name1}' not found"
                        }
                        continue

                    if name2 not in context["results"]:
                        console.print(
                            f"[bold red]Error:[/bold red] Result '{name2}' not found"
                        )
                        context["history"][history_index]["result"] = {
                            "error": f"Result '{name2}' not found"
                        }
                        continue

                    result1 = context["results"][name1]
                    result2 = context["results"][name2]

                    console.print(
                        f"Comparing [bold]{name1}[/bold] ({len(result1.sessions)} sessions) with [bold]{name2}[/bold] ({len(result2.sessions)} sessions)"
                    )

                    # Simple comparison of session counts
                    table = Table(title="Result Comparison")
                    table.add_column("Metric")
                    table.add_column(name1)
                    table.add_column(name2)
                    table.add_column("Difference")

                    session_count1 = len(result1.sessions)
                    session_count2 = len(result2.sessions)
                    table.add_row(
                        "Session Count",
                        str(session_count1),
                        str(session_count2),
                        str(session_count2 - session_count1),
                    )

                    test_count1 = sum(len(s.test_results) for s in result1.sessions)
                    test_count2 = sum(len(s.test_results) for s in result2.sessions)
                    table.add_row(
                        "Test Count",
                        str(test_count1),
                        str(test_count2),
                        str(test_count2 - test_count1),
                    )

                    console.print(table)
                    context["history"][history_index]["result"] = {
                        "summary": f"Compared results {name1} and {name2}"
                    }

                else:
                    console.print(
                        f"[bold red]Error:[/bold red] Unknown result subcommand: {subcommand}"
                    )
                    context["history"][history_index]["result"] = {
                        "error": f"Unknown result subcommand: {subcommand}"
                    }

            # Session commands
            elif user_input.lower().startswith("session."):
                if context["current_result"] is None:
                    console.print(
                        "[bold red]Error:[/bold red] No query results available. Execute a query first."
                    )
                    context["history"][history_index]["result"] = {
                        "error": "No query results"
                    }
                    continue

                parts = user_input.split(".", 1)
                if len(parts) < 2:
                    console.print(
                        "[bold red]Error:[/bold red] Invalid session command format"
                    )
                    context["history"][history_index]["result"] = {
                        "error": "Invalid session command format"
                    }
                    continue

                subcommand = parts[1].strip()

                # Show debug information if debug mode is enabled
                if context["debug_mode"]:
                    console.print(
                        "[bold blue]DEBUG: Executing session operation:[/bold blue]"
                    )
                    if hasattr(context["current_result"], "sessions"):
                        session_count = len(context["current_result"].sessions)
                        console.print(
                            f"[blue]# Processing QueryResult with {session_count} sessions[/blue]"
                        )
                        console.print(f"[blue]# Operation: {subcommand}[/blue]")

                if subcommand == "list":
                    if (
                        not context["current_result"]
                        or not context["current_result"].sessions
                    ):
                        console.print(
                            "[bold red]Error:[/bold red] No active result with sessions"
                        )
                        context["history"][history_index]["result"] = {
                            "error": "No active result with sessions"
                        }
                        continue

                    table = Table(title="Sessions")
                    table.add_column("Session ID")
                    table.add_column("SUT")
                    table.add_column("Start Time")
                    table.add_column("Duration (s)")
                    table.add_column("Tests")

                    for session in context["current_result"].sessions:
                        table.add_row(
                            session.session_id,
                            session.sut_name,
                            str(session.session_start_time),
                            str(round(session.session_duration, 2)),
                            str(len(session.test_results)),
                        )

                    console.print(table)
                    context["history"][history_index]["result"] = {
                        "summary": f"Listed {len(context['current_result'].sessions)} sessions"
                    }

                elif subcommand == "show":
                    if (
                        not context["current_result"]
                        or not context["current_result"].sessions
                    ):
                        console.print(
                            "[bold red]Error:[/bold red] No active result with sessions"
                        )
                        context["history"][history_index]["result"] = {
                            "error": "No active result with sessions"
                        }
                        continue

                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing session ID")
                        context["history"][history_index]["result"] = {
                            "error": "Missing session ID"
                        }
                        continue

                    session_id = parts[2]
                    session = next(
                        (
                            s
                            for s in context["current_result"].sessions
                            if s.id == session_id
                        ),
                        None,
                    )

                    if not session:
                        console.print(
                            f"[bold red]Error:[/bold red] Session '{session_id}' not found"
                        )
                        context["history"][history_index]["result"] = {
                            "error": f"Session '{session_id}' not found"
                        }
                        continue

                    console.print(f"Session: [bold]{session.session_id}[/bold]")
                    console.print(f"SUT: {session.sut_name}")
                    console.print(f"Start Time: {session.session_start_time}")
                    console.print(f"Duration: {session.session_duration}")
                    console.print(f"Tests: {len(session.test_results)}")

                    # Show additional session metadata if available
                    if hasattr(session, "metadata") and session.metadata:
                        console.print("\nMetadata:")
                        for key, value in session.metadata.items():
                            console.print(f"  {key}: {value}")

                    context["history"][history_index]["result"] = {
                        "summary": f"Showed session {session_id}"
                    }

                elif subcommand == "tests":
                    if (
                        not context["current_result"]
                        or not context["current_result"].sessions
                    ):
                        console.print(
                            "[bold red]Error:[/bold red] No active result with sessions"
                        )
                        context["history"][history_index]["result"] = {
                            "error": "No active result with sessions"
                        }
                        continue

                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing session ID")
                        context["history"][history_index]["result"] = {
                            "error": "Missing session ID"
                        }
                        continue

                    session_id = parts[2]
                    session = next(
                        (
                            s
                            for s in context["current_result"].sessions
                            if s.id == session_id
                        ),
                        None,
                    )

                    if not session:
                        console.print(
                            f"[bold red]Error:[/bold red] Session '{session_id}' not found"
                        )
                        context["history"][history_index]["result"] = {
                            "error": f"Session '{session_id}' not found"
                        }
                        continue

                    table = Table(title=f"Tests in Session {session.session_id}")
                    table.add_column("Test ID")
                    table.add_column("Nodeid")
                    table.add_column("Outcome")
                    table.add_column("Duration (s)")

                    for test in session.test_results:
                        table.add_row(
                            test.id,
                            test.nodeid,
                            test.outcome,
                            (
                                str(round(test.duration, 3))
                                if test.duration is not None
                                else "N/A"
                            ),
                        )

                    console.print(table)
                    context["history"][history_index]["result"] = {
                        "summary": f"Listed {len(session.test_results)} tests in session {session_id}"
                    }

                elif subcommand == "failures":
                    if (
                        not context["current_result"]
                        or not context["current_result"].sessions
                    ):
                        console.print(
                            "[bold red]Error:[/bold red] No active result with sessions"
                        )
                        context["history"][history_index]["result"] = {
                            "error": "No active result with sessions"
                        }
                        continue

                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing session ID")
                        context["history"][history_index]["result"] = {
                            "error": "Missing session ID"
                        }
                        continue

                    session_id = parts[2]
                    session = next(
                        (
                            s
                            for s in context["current_result"].sessions
                            if s.id == session_id
                        ),
                        None,
                    )

                    if not session:
                        console.print(
                            f"[bold red]Error:[/bold red] Session '{session_id}' not found"
                        )
                        context["history"][history_index]["result"] = {
                            "error": f"Session '{session_id}' not found"
                        }
                        continue

                    failures = [
                        t for t in session.test_results if t.outcome == "failed"
                    ]

                    if not failures:
                        console.print(f"No failures in session {session.session_id}")
                        context["history"][history_index]["result"] = {
                            "summary": f"No failures in session {session_id}"
                        }
                        continue

                    table = Table(title=f"Failures in Session {session.session_id}")
                    table.add_column("Test ID")
                    table.add_column("Nodeid")
                    table.add_column("Duration (s)")

                    for test in failures:
                        table.add_row(
                            test.id,
                            test.nodeid,
                            (
                                str(round(test.duration, 3))
                                if test.duration is not None
                                else "N/A"
                            ),
                        )

                    console.print(table)

                    # Show failure details
                    for i, test in enumerate(failures):
                        if hasattr(test, "longrepr") and test.longrepr:
                            console.print(
                                f"\n[bold red]Failure {i+1}:[/bold red] {test.nodeid}"
                            )
                            console.print(test.longrepr)

                    context["history"][history_index]["result"] = {
                        "summary": f"Listed {len(failures)} failures in session {session_id}"
                    }

                else:
                    console.print(
                        f"[bold red]Error:[/bold red] Unknown session subcommand: {subcommand}"
                    )
                    context["history"][history_index]["result"] = {
                        "error": f"Unknown session subcommand: {subcommand}"
                    }

            # Python command - execute Python code directly
            elif user_input.lower().startswith("python "):
                python_code = user_input[7:].strip()
                if not python_code:
                    console.print(
                        "[bold red]Error:[/bold red] Missing Python expression"
                    )
                    context["history"][history_index]["result"] = {
                        "error": "Missing Python expression"
                    }
                    continue

                try:
                    # Execute the Python code in the context of the shell
                    result = eval(python_code, globals(), context)

                    # Display the result
                    console.print(
                        "[bold green]Python expression executed:[/bold green]"
                    )

                    # Format the result for display
                    if result is not None:
                        if isinstance(result, (dict, list)):
                            _format_rich_output(result, title="Result")
                        else:
                            console.print(f"Result: {result}")

                    context["history"][history_index]["result"] = {
                        "action": "executed Python expression",
                        "expression": python_code,
                        "result": str(result) if result is not None else "None",
                    }
                except Exception as e:
                    console.print(
                        f"[bold red]Error executing Python expression:[/bold red] {str(e)}"
                    )
                    console.print(traceback.format_exc(), style="red")
                    context["history"][history_index]["result"] = {"error": str(e)}
                continue

            # API commands for direct core API access
            elif user_input.lower().startswith("api "):
                parts = user_input.lower().split(" ", 2)
                if len(parts) < 2:
                    console.print("[bold red]Error:[/bold red] Missing API subcommand")
                    context["history"][history_index]["result"] = {
                        "error": "Missing API subcommand"
                    }
                    continue

                subcommand = parts[1].lower()

                if subcommand == "help":
                    console.print("\n[bold]Core API Direct Access:[/bold]")
                    console.print(
                        "The interactive shell provides direct access to the pytest-insight core API classes."
                    )
                    console.print(
                        "You can use these classes directly in Python expressions or with the api commands."
                    )

                    console.print("\n[bold cyan]Available Core Classes:[/bold cyan]")
                    console.print("  Query       - Find and filter test sessions")
                    console.print("  Analysis    - Analyze test results")
                    console.print("  Comparison  - Compare test results")
                    console.print("  Insights    - Generate comprehensive insights")
                    console.print("  InsightAPI  - Unified API for all components")

                    console.print(
                        "\n[bold cyan]Using Core Classes with Python Commands:[/bold cyan]"
                    )
                    console.print(
                        "  python Query().with_profile('default').in_last_days(7).execute()"
                    )
                    console.print(
                        "  python InsightAPI().query().in_last_days(7).execute()"
                    )
                    console.print("  query('default').in_last_days(7).execute()")

                    console.print(
                        "\n[bold cyan]Using Core API Factory Functions:[/bold cyan]"
                    )
                    console.print("  python query()      - Create a new Query instance")
                    console.print(
                        "  python compare()    - Create a new Comparison instance"
                    )
                    console.print(
                        "  python analyze()    - Create a new Analysis instance"
                    )
                    console.print(
                        "  python get_insights() - Create a new Insights instance"
                    )

                    console.print("\n[bold cyan]Direct Method Execution:[/bold cyan]")
                    console.print(
                        "  api exec query in_last_days 7    - Execute method on current query object"
                    )
                    console.print(
                        "  api exec analysis health_report  - Execute method on current analysis object"
                    )
                    console.print(
                        "  api exec comparison compare_suts my-app1 my-app2 - Execute with arguments"
                    )

                    context["history"][history_index]["result"] = {
                        "action": "showed API help"
                    }

                elif subcommand == "query":
                    # Create a new Query instance using the core API
                    profile_name = context["active_profile"]
                    if len(parts) > 2:
                        profile_name = parts[2]

                    result = core_query(profile_name)
                    context["current_query"] = result

                    console.print(
                        f"[bold green]Created new Query instance with profile '{profile_name}'[/bold green]"
                    )
                    console.print("Use 'query chain' to see the current query chain")
                    console.print(
                        "Use 'python' commands to work with the query directly"
                    )

                    context["history"][history_index]["result"] = {
                        "action": "created Query instance",
                        "profile": profile_name,
                    }

                elif subcommand == "compare":
                    # Create a new Comparison instance using the core API
                    profile_name = context["active_profile"]
                    if len(parts) > 2:
                        profile_name = parts[2]

                    result = core_compare(profile_name)
                    context["current_comparison"] = result

                    console.print(
                        f"[bold green]Created new Comparison instance with profile '{profile_name}'[/bold green]"
                    )
                    console.print(
                        "Use 'python' commands to work with the comparison directly"
                    )

                    context["history"][history_index]["result"] = {
                        "action": "created Comparison instance",
                        "profile": profile_name,
                    }

                elif subcommand == "analyze":
                    # Create a new Analysis instance using the core API
                    profile_name = context["active_profile"]
                    if len(parts) > 2:
                        profile_name = parts[2]

                    result = core_analyze(profile_name)
                    context["current_analysis"] = result

                    console.print(
                        f"[bold green]Created new Analysis instance with profile '{profile_name}'[/bold green]"
                    )
                    console.print(
                        "Use 'python' commands to work with the analysis directly"
                    )

                    context["history"][history_index]["result"] = {
                        "action": "created Analysis instance",
                        "profile": profile_name,
                    }

                elif subcommand == "insights":
                    # Create a new Insights instance using the core API
                    profile_name = context["active_profile"]
                    if len(parts) > 2:
                        profile_name = parts[2]

                    result = core_get_insights(profile_name)
                    context["current_insights"] = result

                    console.print(
                        f"[bold green]Created new Insights instance with profile '{profile_name}'[/bold green]"
                    )
                    console.print(
                        "Use 'python' commands to work with the insights directly"
                    )

                    context["history"][history_index]["result"] = {
                        "action": "created Insights instance",
                        "profile": profile_name,
                    }

                elif subcommand == "exec":
                    # Execute a method on a core API object
                    if len(parts) < 2:
                        console.print(
                            "[bold red]Error:[/bold red] Missing object and method specification"
                        )
                        console.print("Usage: api exec [object] [method] [args...]")
                        context["history"][history_index]["result"] = {
                            "error": "Missing object and method specification"
                        }
                        continue

                    # Parse the command: api exec [object] [method] [args...]
                    exec_parts = user_input.split(" ", 3)[2:]  # Skip 'api exec'

                    if len(exec_parts) < 2:
                        console.print(
                            "[bold red]Error:[/bold red] Missing object or method name"
                        )
                        console.print("Usage: api exec [object] [method] [args...]")
                        context["history"][history_index]["result"] = {
                            "error": "Missing object or method name"
                        }
                        continue

                    obj_name = exec_parts[0].lower()
                    method_name = exec_parts[1]

                    # Parse arguments if any
                    args = []
                    if len(exec_parts) > 2:
                        arg_str = exec_parts[2]
                        # Simple argument parsing - split by spaces for positional args
                        raw_args = [arg.strip() for arg in arg_str.split()]

                        # Convert arguments to appropriate types
                        for arg in raw_args:
                            try:
                                if arg.lower() == "true":
                                    args.append(True)
                                elif arg.lower() == "false":
                                    args.append(False)
                                elif arg.isdigit():
                                    args.append(int(arg))
                                elif arg.replace(".", "", 1).isdigit():
                                    args.append(float(arg))
                                else:
                                    args.append(arg)
                            except Exception:
                                args.append(arg)

                    # Get the object to execute the method on
                    target_obj = None
                    if obj_name == "query":
                        target_obj = context.get("current_query")
                        if target_obj is None:
                            console.print(
                                "[bold red]Error:[/bold red] No active Query object"
                            )
                            console.print(
                                "Create one first with 'api query' or 'query new'"
                            )
                            context["history"][history_index]["result"] = {
                                "error": "No active Query object"
                            }
                            continue
                    elif obj_name == "analysis":
                        target_obj = context.get("current_analysis")
                        if target_obj is None:
                            console.print(
                                "[bold red]Error:[/bold red] No active Analysis object"
                            )
                            console.print("Create one first with 'api analyze'")
                            context["history"][history_index]["result"] = {
                                "error": "No active Analysis object"
                            }
                            continue
                    elif obj_name == "comparison":
                        target_obj = context.get("current_comparison")
                        if target_obj is None:
                            console.print(
                                "[bold red]Error:[/bold red] No active Comparison object"
                            )
                            console.print("Create one first with 'api compare'")
                            context["history"][history_index]["result"] = {
                                "error": "No active Comparison object"
                            }
                            continue
                    elif obj_name == "insights":
                        target_obj = context.get("current_insights")
                        if target_obj is None:
                            console.print(
                                "[bold red]Error:[/bold red] No active Insights object"
                            )
                            console.print("Create one first with 'api insights'")
                            context["history"][history_index]["result"] = {
                                "error": "No active Insights object"
                            }
                            continue
                    else:
                        console.print(
                            f"[bold red]Error:[/bold red] Unknown object type: {obj_name}"
                        )
                        console.print(
                            "Available objects: query, analysis, comparison, insights"
                        )
                        context["history"][history_index]["result"] = {
                            "error": f"Unknown object type: {obj_name}"
                        }
                        continue

                    # Check if the method exists
                    if not hasattr(target_obj, method_name):
                        console.print(
                            f"[bold red]Error:[/bold red] Method '{method_name}' not found on {obj_name} object"
                        )

                        # Show available methods
                        methods = [
                            name
                            for name, member in inspect.getmembers(target_obj.__class__)
                            if inspect.isfunction(member) and not name.startswith("_")
                        ]

                        console.print("[bold]Available methods:[/bold]")
                        for method in methods:
                            console.print(f"  {method}")

                        context["history"][history_index]["result"] = {
                            "error": f"Method '{method_name}' not found"
                        }
                        continue

                    # Get the method
                    method = getattr(target_obj, method_name)

                    # Show debug information if debug mode is enabled
                    if context["debug_mode"]:
                        console.print(
                            "[bold blue]DEBUG: Executing API method call:[/bold blue]"
                        )
                        arg_display = ", ".join([repr(a) for a in args])
                        api_call = f"{obj_name}.{method_name}({arg_display})"
                        console.print(f"[blue]{api_call}[/blue]")

                    try:
                        # Execute the method
                        result = method(*args)

                        # Handle the result
                        console.print(
                            f"[bold green]Method {method_name} executed successfully[/bold green]"
                        )

                        # Store the result if it's a new object of a known type
                        if isinstance(result, Query):
                            context["current_query"] = result
                            console.print("Updated current query with the result")
                        elif isinstance(result, Analysis):
                            context["current_analysis"] = result
                            console.print("Updated current analysis with the result")
                        elif isinstance(result, Comparison):
                            context["current_comparison"] = result
                            console.print("Updated current comparison with the result")
                        elif isinstance(result, Insights):
                            context["current_insights"] = result
                            console.print("Updated current insights with the result")

                        # Display the result
                        if result is not None:
                            if isinstance(result, (dict, list)):
                                _format_rich_output(
                                    result, title=f"Result of {method_name}"
                                )
                            else:
                                console.print(f"Result: {result}")

                        context["history"][history_index]["result"] = {
                            "action": f"executed {obj_name}.{method_name}",
                            "args": args,
                            "result_type": (
                                type(result).__name__ if result is not None else "None"
                            ),
                        }
                    except Exception as e:
                        console.print(
                            f"[bold red]Error executing {method_name}:[/bold red] {str(e)}"
                        )
                        console.print(traceback.format_exc(), style="red")
                        context["history"][history_index]["result"] = {"error": str(e)}

                else:
                    console.print(
                        f"[bold red]Error:[/bold red] Unknown API subcommand: {subcommand}"
                    )
                    console.print(
                        "Available subcommands: help, query, compare, analyze, insights, exec"
                    )
                    context["history"][history_index]["result"] = {
                        "error": f"Unknown API subcommand: {subcommand}"
                    }

                continue

            # Debug command
            elif user_input.lower().startswith("debug"):
                parts = user_input.lower().split()
                if len(parts) < 2:
                    console.print(
                        "[bold red]Error:[/bold red] Debug command requires an argument (on, off, or status)"
                    )
                    context["history"][history_index]["result"] = {
                        "error": "Missing debug argument"
                    }
                    continue

                debug_action = parts[1]
                if debug_action == "on":
                    context["debug_mode"] = True
                    console.print("[bold green]Debug mode enabled[/bold green]")
                    context["history"][history_index]["result"] = {
                        "action": "debug mode enabled"
                    }
                elif debug_action == "off":
                    context["debug_mode"] = False
                    console.print("[bold yellow]Debug mode disabled[/bold yellow]")
                    context["history"][history_index]["result"] = {
                        "action": "debug mode disabled"
                    }
                elif debug_action == "status":
                    status = "enabled" if context["debug_mode"] else "disabled"
                    console.print(
                        f"[bold blue]Debug mode is currently {status}[/bold blue]"
                    )
                    context["history"][history_index]["result"] = {
                        "status": f"debug mode {status}"
                    }
                else:
                    console.print(
                        "[bold red]Error:[/bold red] Invalid debug argument. Use 'on', 'off', or 'status'"
                    )
                    context["history"][history_index]["result"] = {
                        "error": "Invalid debug argument"
                    }
                continue

            # Unknown command
            else:
                console.print(f"[bold red]Error:[/bold red] Unknown command: {command}")
                context["history"][history_index]["result"] = {
                    "error": f"Unknown command: {command}"
                }

        except KeyboardInterrupt:
            # Handle Ctrl+C
            console.print("\nUse 'exit' or 'quit' to exit the shell.")
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")
            console.print(traceback.format_exc(), style="red")
            context["history"][history_index]["result"] = {"error": str(e)}


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Developer tools for exploring the pytest-insight API."""
    if ctx.invoked_subcommand is None:
        # Start interactive shell if no subcommand was provided
        _start_interactive_shell()


@app.command(
    "shell", help="Start an interactive shell for exploring the pytest-insight API"
)
def interactive_shell():
    """Start an interactive shell for exploring the pytest-insight API."""
    try:
        # Just check if prompt_toolkit is available
        import importlib.util

        if importlib.util.find_spec("prompt_toolkit") is None:
            raise ImportError("prompt_toolkit not found")
    except ImportError:
        console = Console()
        console.print(
            "[bold red]Error:[/bold red] prompt_toolkit is required for the interactive shell."
        )
        console.print("Please install it with: pip install prompt-toolkit")
        return

    _start_interactive_shell()


# Register API commands
_register_api_commands()


@app.command("compare")
def cli_compare(
    base_sut: str = typer.Option(..., help="Base SUT name"),
    target_sut: str = typer.Option(..., help="Target SUT name"),
    days: Optional[int] = typer.Option(None, help="Number of days to look back"),
    test_pattern: Optional[str] = typer.Option(
        None, help="Test pattern (supports wildcards)"
    ),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
    format: OutputFormat = typer.Option(
        OutputFormat.TEXT, help="Output format (text or json)"
    ),
):
    """Compare test results between two SUTs.

    This command performs a comparison between test results from two SUTs,
    identifying new failures, fixed tests, flaky tests, and performance changes.
    """
    console = Console()

    try:
        # Create comparison instance with optional profile
        from pytest_insight.core.comparison import comparison

        comp = comparison(base_profile=profile, target_profile=profile)

        # Configure the comparison
        comp = comp.between_suts(base_sut, target_sut)

        # Apply days filter if specified
        if days is not None:
            comp = comp.apply_to_both(lambda q: q.in_last_days(days))

        # Apply test pattern filter if specified
        if test_pattern is not None:
            comp = comp.apply_to_both(
                lambda q: q.filter_by_test().with_pattern(test_pattern).apply()
            )

        # Execute the comparison
        result = comp.execute()

        # Format and display results
        if format == OutputFormat.JSON:
            import json

            # Convert result to JSON-serializable dict
            result_dict = {
                "new_failures": result.new_failures,
                "new_passes": result.new_passes,
                "flaky_tests": result.flaky_tests,
                "slower_tests": result.slower_tests,
                "faster_tests": result.faster_tests,
                "missing_tests": result.missing_tests,
                "new_tests": result.new_tests,
                "base_session": {
                    "id": result.base_session.id,
                    "sut": result.base_session.sut,
                    "timestamp": str(result.base_session.timestamp),
                    "test_count": len(result.base_session.test_results),
                },
                "target_session": {
                    "id": result.target_session.id,
                    "sut": result.target_session.sut,
                    "timestamp": str(result.target_session.timestamp),
                    "test_count": len(result.target_session.test_results),
                },
            }

            print(json.dumps(result_dict, indent=2))
        else:
            # Rich text output
            console.print(
                f"\n[bold blue]Comparison Results: [/bold blue][yellow]{base_sut}[/yellow] vs [green]{target_sut}[/green]\n"
            )

            # Create a table for the summary
            table = Table(
                title="Comparison Summary",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Category", style="cyan")
            table.add_column("Count", style="green")
            table.add_column("Details", style="yellow")

            # Add rows for each category
            table.add_row(
                "New Failures",
                str(len(result.new_failures)),
                ", ".join(result.new_failures[:5])
                + ("..." if len(result.new_failures) > 5 else ""),
            )
            table.add_row(
                "Fixed Tests",
                str(len(result.new_passes)),
                ", ".join(result.new_passes[:5])
                + ("..." if len(result.new_passes) > 5 else ""),
            )
            table.add_row(
                "Flaky Tests",
                str(len(result.flaky_tests)),
                ", ".join(result.flaky_tests[:5])
                + ("..." if len(result.flaky_tests) > 5 else ""),
            )
            table.add_row(
                "Slower Tests",
                str(len(result.slower_tests)),
                ", ".join(result.slower_tests[:5])
                + ("..." if len(result.slower_tests) > 5 else ""),
            )
            table.add_row(
                "Faster Tests",
                str(len(result.faster_tests)),
                ", ".join(result.faster_tests[:5])
                + ("..." if len(result.faster_tests) > 5 else ""),
            )
            table.add_row(
                "Missing Tests",
                str(len(result.missing_tests)),
                ", ".join(result.missing_tests[:5])
                + ("..." if len(result.missing_tests) > 5 else ""),
            )
            table.add_row(
                "New Tests",
                str(len(result.new_tests)),
                ", ".join(result.new_tests[:5])
                + ("..." if len(result.new_tests) > 5 else ""),
            )

            console.print(table)

            # Session information
            console.print("\n[bold]Session Information:[/bold]")
            console.print(
                f"  Base: [cyan]{result.base_session.sut}[/cyan] ({result.base_session.timestamp})"
            )
            console.print(
                f"  Target: [cyan]{result.target_session.sut}[/cyan] ({result.target_session.timestamp})"
            )

            # Provide guidance on next steps
            if result.has_changes():
                console.print("\n[bold green]Suggested Next Steps:[/bold green]")
                if result.new_failures:
                    console.print(
                        "  - Investigate new failures with: insight analyze --sut",
                        target_sut,
                    )
                if result.flaky_tests:
                    console.print(
                        "  - Analyze flaky tests with: insight analyze --flaky-only --sut",
                        target_sut,
                    )
            else:
                console.print(
                    "\n[bold green]No significant changes detected between the SUTs.[/bold green]"
                )

    except Exception as e:
        if format == OutputFormat.JSON:
            import json

            print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")
            console.print(traceback.format_exc(), style="red")


@app.command("analyze")
def cli_analyze(
    sut: Optional[str] = typer.Option(None, help="System Under Test name"),
    days: Optional[int] = typer.Option(7, help="Number of days to analyze"),
    test_pattern: Optional[str] = typer.Option(
        None, help="Test pattern (supports wildcards)"
    ),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
    report_type: str = typer.Option(
        "health", help="Type of report (health, stability, performance, flaky)"
    ),
    flaky_only: bool = typer.Option(False, help="Focus only on flaky tests"),
    format: OutputFormat = typer.Option(
        OutputFormat.TEXT, help="Output format (text or json)"
    ),
):
    """Analyze test results for a specific SUT.

    This command performs analysis on test results, providing insights into
    test health, stability, performance, and flakiness.
    """
    console = Console()

    try:
        # Create analysis instance with optional profile
        from pytest_insight.core.analysis import analysis

        # Initialize analysis with profile if specified
        if profile:
            analyzer = analysis(profile_name=profile)
        else:
            analyzer = analysis()

        # Apply SUT filter if specified
        if sut:
            analyzer = analyzer.for_sut(sut)

        # Apply days filter
        analyzer = analyzer.in_last_days(days)

        # Apply test pattern filter if specified
        if test_pattern:
            analyzer = analyzer.with_test_pattern(test_pattern)

        # Execute the appropriate analysis based on report type
        if report_type == "health":
            result = analyzer.health_report()

            if format == OutputFormat.JSON:
                import json

                # Convert result to JSON-serializable dict
                result_dict = {
                    "pass_rate": result.pass_rate,
                    "failure_rate": result.failure_rate,
                    "skip_rate": result.skip_rate,
                    "error_rate": result.error_rate,
                    "flaky_rate": result.flaky_rate,
                    "total_tests": result.total_tests,
                    "total_sessions": result.total_sessions,
                    "days_analyzed": days,
                }

                print(json.dumps(result_dict, indent=2))
            else:
                # Rich text output for health report
                title_parts = ["\n[bold blue]Health Report"]
                if sut:
                    title_parts.append(f" for [yellow]{sut}[/yellow]")
                title_parts.append(f" (Last {days} days)\n")
                console.print("".join(title_parts))

                # Create a table for the health metrics
                table = Table(
                    title="Test Health Metrics",
                    show_header=True,
                    header_style="bold magenta",
                )
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")

                # Add rows for each metric
                table.add_row("Pass Rate", f"{result.pass_rate:.1%}")
                table.add_row("Failure Rate", f"{result.failure_rate:.1%}")
                table.add_row("Skip Rate", f"{result.skip_rate:.1%}")
                table.add_row("Error Rate", f"{result.error_rate:.1%}")
                table.add_row("Flaky Rate", f"{result.flaky_rate:.1%}")
                table.add_row("Total Tests", str(result.total_tests))
                table.add_row("Total Sessions", str(result.total_sessions))

                console.print(table)

                # Health assessment
                if result.pass_rate >= 0.95:
                    console.print(
                        "\n[bold green]Overall Health: Excellent[/bold green]"
                    )
                    console.print("Test suite is performing well with high pass rates.")
                elif result.pass_rate >= 0.85:
                    console.print("\n[bold yellow]Overall Health: Good[/bold yellow]")
                    console.print(
                        "Test suite is generally healthy but has room for improvement."
                    )
                else:
                    console.print(
                        "\n[bold red]Overall Health: Needs Attention[/bold red]"
                    )
                    console.print(
                        "Test suite has significant issues that should be addressed."
                    )

                # Recommendations
                console.print("\n[bold]Recommendations:[/bold]")
                if result.flaky_rate > 0.05:
                    console.print(
                        "  - [yellow]High flakiness detected.[/yellow] Run 'insight analyze --report-type flaky' to identify flaky tests."
                    )
                if result.failure_rate > 0.1:
                    console.print(
                        "  - [red]High failure rate detected.[/red] Run 'insight analyze --report-type stability' to identify consistently failing tests."
                    )

        elif report_type == "stability":
            # Get consistently failing and flaky tests
            failing_tests = analyzer.identify_consistently_failing_tests()
            flaky_tests = analyzer.identify_flaky_tests()

            if format == OutputFormat.JSON:
                import json

                result_dict = {
                    "consistently_failing_tests": failing_tests,
                    "flaky_tests": flaky_tests,
                    "days_analyzed": days,
                }

                print(json.dumps(result_dict, indent=2))
            else:
                # Rich text output for stability report
                title_parts = ["\n[bold blue]Stability Report"]
                if sut:
                    title_parts.append(f" for [yellow]{sut}[/yellow]")
                title_parts.append(f" (Last {days} days)\n")
                console.print("".join(title_parts))

                if failing_tests:
                    table = Table(
                        title="Consistently Failing Tests",
                        show_header=True,
                        header_style="bold red",
                    )
                    table.add_column("Test", style="cyan")

                    for test in failing_tests[:20]:  # Limit to 20 tests for readability
                        table.add_row(test)

                    if len(failing_tests) > 20:
                        table.add_row(f"... and {len(failing_tests) - 20} more")

                    console.print(table)
                else:
                    console.print("[green]No consistently failing tests found.[/green]")

                if flaky_tests:
                    table = Table(
                        title="Flaky Tests",
                        show_header=True,
                        header_style="bold yellow",
                    )
                    table.add_column("Test", style="cyan")

                    for test in flaky_tests[:20]:  # Limit to 20 tests for readability
                        table.add_row(test)

                    if len(flaky_tests) > 20:
                        table.add_row(f"... and {len(flaky_tests) - 20} more")

                    console.print(table)
                else:
                    console.print("[green]No flaky tests found.[/green]")

        elif report_type == "performance":
            # Get slowest tests
            slowest_tests = analyzer.get_slowest_tests(limit=20)

            if format == OutputFormat.JSON:
                import json

                result_dict = {
                    "slowest_tests": [
                        {"nodeid": test.nodeid, "duration": test.duration}
                        for test in slowest_tests
                    ],
                    "days_analyzed": days,
                }

                print(json.dumps(result_dict, indent=2))
            else:
                # Rich text output for performance report
                title_parts = ["\n[bold blue]Performance Report"]
                if sut:
                    title_parts.append(f" for [yellow]{sut}[/yellow]")
                title_parts.append(f" (Last {days} days)\n")
                console.print("".join(title_parts))

                if slowest_tests:
                    table = Table(
                        title="Slowest Tests",
                        show_header=True,
                        header_style="bold magenta",
                    )
                    table.add_column("Test", style="cyan")
                    table.add_column("Duration (s)", style="green", justify="right")

                    for test in slowest_tests:
                        table.add_row(test.nodeid, f"{test.duration:.2f}")

                    console.print(table)

                    # Recommendations
                    console.print("\n[bold]Performance Recommendations:[/bold]")
                    console.print(
                        "  - Consider optimizing tests that take longer than 1 second"
                    )
                    console.print(
                        "  - Look for common patterns in slow tests (e.g., database access, file I/O)"
                    )
                else:
                    console.print("[yellow]No test duration data available.[/yellow]")

        elif report_type == "flaky":
            # Focus specifically on flaky tests
            flaky_tests = analyzer.identify_flaky_tests()

            if format == OutputFormat.JSON:
                import json

                result_dict = {
                    "flaky_tests": flaky_tests,
                    "count": len(flaky_tests),
                    "days_analyzed": days,
                }

                print(json.dumps(result_dict, indent=2))
            else:
                # Rich text output for flaky tests report
                title_parts = ["\n[bold blue]Flaky Tests Report"]
                if sut:
                    title_parts.append(f" for [yellow]{sut}[/yellow]")
                title_parts.append(f" (Last {days} days)\n")
                console.print("".join(title_parts))

                if flaky_tests:
                    table = Table(
                        title=f"Flaky Tests ({len(flaky_tests)} found)",
                        show_header=True,
                        header_style="bold yellow",
                    )
                    table.add_column("Test", style="cyan")

                    for test in flaky_tests[:30]:  # Limit to 30 tests for readability
                        table.add_row(test)

                    if len(flaky_tests) > 30:
                        table.add_row(f"... and {len(flaky_tests) - 30} more")

                    console.print(table)

                    # Recommendations for flaky tests
                    console.print(
                        "\n[bold]Recommendations for Addressing Flaky Tests:[/bold]"
                    )
                    console.print(
                        "  1. [yellow]Identify patterns[/yellow] - Look for common factors (async, timing, resources)"
                    )
                    console.print(
                        "  2. [yellow]Isolate and reproduce[/yellow] - Try to reproduce the flakiness locally"
                    )
                    console.print(
                        "  3. [yellow]Add logging[/yellow] - Enhance logging to capture more context when tests fail"
                    )
                    console.print(
                        "  4. [yellow]Consider quarantine[/yellow] - Move highly flaky tests to a separate suite"
                    )
                else:
                    console.print(
                        "[green]No flaky tests found in the analyzed period.[/green]"
                    )

        else:
            console.print(
                f"[bold red]Error:[/bold red] Unknown report type: {report_type}"
            )
            console.print(
                "Available report types: health, stability, performance, flaky"
            )

    except Exception as e:
        if format == OutputFormat.JSON:
            import json

            print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")
            console.print(traceback.format_exc(), style="red")


@app.command("generate_insights")
def cli_generate_insights(
    sut: Optional[str] = typer.Option(None, help="System Under Test name"),
    days: Optional[int] = typer.Option(7, help="Number of days to analyze"),
    test_pattern: Optional[str] = typer.Option(
        None, help="Test pattern (supports wildcards)"
    ),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
    insight_type: str = typer.Option(
        "summary", help="Type of insights (summary, patterns, trends, dependencies)"
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.TEXT, help="Output format (text or json)"
    ),
):
    """Generate insights from test data.

    This command generates various types of insights from test data, including summary reports, error patterns, stability trends, and test dependencies.
    """
    console = Console()

    try:
        # Create API instance
        api = InsightAPI()
        if profile:
            api = api.with_profile(profile)

        # Build query
        query = api.query()
        if sut:
            query = query.with_sut(sut)
        query = query.in_last_days(days)
        if test_pattern:
            query = query.with_test_pattern(test_pattern)

        # Create insights instance with the query
        insight_api = api.insights().with_query(query)

        # Set up console for rich output
        console = Console()

        # Execute the appropriate insights based on insight type
        if insight_type == "summary":
            result = insight_api.summary_report()

            if format == OutputFormat.JSON:
                import json

                # Convert result to JSON-serializable dict
                result_dict = {
                    "test_count": result.test_count,
                    "session_count": result.session_count,
                    "pass_rate": result.pass_rate,
                    "flaky_rate": result.flaky_rate,
                    "top_failures": result.top_failures,
                    "top_flaky": result.top_flaky,
                    "performance_issues": result.performance_issues,
                    "days_analyzed": days,
                }

                print(json.dumps(result_dict, indent=2))
            else:
                # Rich text output for summary report
                title_parts = ["\n[bold blue]Summary Insights Report"]
                if sut:
                    title_parts.append(f" for [yellow]{sut}[/yellow]")
                title_parts.append(f" (Last {days} days)\n")
                console.print("".join(title_parts))

                # Create a table for the summary metrics
                table = Table(
                    title="Test Suite Overview",
                    show_header=True,
                    header_style="bold magenta",
                )
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")

                # Add rows for each metric
                table.add_row("Test Count", str(result.test_count))
                table.add_row("Session Count", str(result.session_count))
                table.add_row("Pass Rate", f"{result.pass_rate:.1%}")
                table.add_row("Flaky Rate", f"{result.flaky_rate:.1%}")

                console.print(table)

                # Top failures
                if result.top_failures:
                    console.print("\n[bold red]Top Failing Tests:[/bold red]")
                    for i, test in enumerate(result.top_failures[:5], 1):
                        console.print(f"  {i}. {test}")

                # Top flaky tests
                if result.top_flaky:
                    console.print("\n[bold yellow]Top Flaky Tests:[/bold yellow]")
                    for i, test in enumerate(result.top_flaky[:5], 1):
                        console.print(f"  {i}. {test}")

                # Performance issues
                if result.performance_issues:
                    console.print("\n[bold cyan]Performance Issues:[/bold cyan]")
                    for i, issue in enumerate(result.performance_issues[:5], 1):
                        console.print(f"  {i}. {issue}")

                # Overall assessment
                console.print("\n[bold]Overall Assessment:[/bold]")
                if result.pass_rate >= 0.95 and result.flaky_rate < 0.02:
                    console.print(
                        "[bold green]Excellent[/bold green] - Test suite is healthy and stable."
                    )
                elif result.pass_rate >= 0.85 and result.flaky_rate < 0.05:
                    console.print(
                        "[bold yellow]Good[/bold yellow] - Test suite is generally healthy with minor issues."
                    )
                else:
                    console.print(
                        "[bold red]Needs Attention[/bold red] - Test suite has significant issues to address."
                    )

                # Recommendations
                console.print("\n[bold]Recommended Actions:[/bold]")
                if result.top_failures:
                    console.print(
                        "  - Investigate top failing tests with: insight analyze --report-type stability"
                    )
                if result.top_flaky:
                    console.print(
                        "  - Address flaky tests with: insight analyze --report-type flaky"
                    )
                if result.performance_issues:
                    console.print(
                        "  - Optimize slow tests with: insight analyze --report-type performance"
                    )

        elif insight_type == "patterns":
            result = insight_api.test_insights().error_patterns()

            if format == OutputFormat.JSON:
                import json

                # Convert result to JSON-serializable dict
                result_dict = {
                    "error_patterns": result.patterns,
                    "days_analyzed": days,
                }

                print(json.dumps(result_dict, indent=2))
            else:
                # Rich text output for error patterns
                title_parts = ["\n[bold blue]Error Pattern Insights"]
                if sut:
                    title_parts.append(f" for [yellow]{sut}[/yellow]")
                title_parts.append(f" (Last {days} days)\n")
                console.print("".join(title_parts))

                if result.patterns:
                    table = Table(
                        title="Common Error Patterns",
                        show_header=True,
                        header_style="bold red",
                    )
                    table.add_column("Pattern", style="cyan")
                    table.add_column("Frequency", style="green", justify="right")
                    table.add_column("Example Tests", style="yellow")

                    for pattern in result.patterns[
                        :10
                    ]:  # Limit to 10 patterns for readability
                        example_tests = ", ".join(pattern.example_tests[:2])
                        if len(pattern.example_tests) > 2:
                            example_tests += "..."
                        table.add_row(
                            pattern.pattern, str(pattern.frequency), example_tests
                        )

                    console.print(table)

                    # Recommendations
                    console.print("\n[bold]Pattern Analysis Recommendations:[/bold]")
                    console.print(
                        "  - Look for common root causes in tests with similar error patterns"
                    )
                    console.print(
                        "  - Consider refactoring test fixtures or setup code for recurring patterns"
                    )
                else:
                    console.print(
                        "[green]No significant error patterns found in the analyzed period.[/green]"
                    )

        elif insight_type == "trends":
            result = insight_api.test_insights().stability_timeline()

            if format == OutputFormat.JSON:
                import json

                # Convert result to JSON-serializable dict
                result_dict = {
                    "timeline": [
                        {
                            "date": str(point.date),
                            "pass_rate": point.pass_rate,
                            "flaky_rate": point.flaky_rate,
                        }
                        for point in result.timeline
                    ],
                    "trend": result.trend,
                    "days_analyzed": days,
                }

                print(json.dumps(result_dict, indent=2))
            else:
                # Rich text output for stability timeline
                title_parts = ["\n[bold blue]Stability Trend Insights"]
                if sut:
                    title_parts.append(f" for [yellow]{sut}[/yellow]")
                title_parts.append(f" (Last {days} days)\n")
                console.print("".join(title_parts))

                if result.timeline:
                    table = Table(
                        title="Stability Timeline",
                        show_header=True,
                        header_style="bold magenta",
                    )
                    table.add_column("Date", style="cyan")
                    table.add_column("Pass Rate", style="green")
                    table.add_column("Flaky Rate", style="yellow")

                    for point in result.timeline:
                        table.add_row(
                            str(point.date),
                            f"{point.pass_rate:.1%}",
                            f"{point.flaky_rate:.1%}",
                        )

                    console.print(table)

                    # Trend assessment
                    console.print("\n[bold]Trend Assessment:[/bold]")
                    if result.trend == "improving":
                        console.print(
                            "[bold green]Improving[/bold green] - Test stability is trending upward."
                        )
                    elif result.trend == "stable":
                        console.print(
                            "[bold blue]Stable[/bold blue] - Test stability is consistent."
                        )
                    elif result.trend == "declining":
                        console.print(
                            "[bold red]Declining[/bold red] - Test stability is trending downward."
                        )
                    else:
                        console.print(
                            "[bold yellow]Inconclusive[/bold yellow] - Not enough data to determine trend."
                        )
                else:
                    console.print(
                        "[yellow]Insufficient data for trend analysis.[/yellow]"
                    )

        elif insight_type == "dependencies":
            result = insight_api.test_insights().dependency_graph()

            if format == OutputFormat.JSON:
                import json

                # Convert result to JSON-serializable dict
                result_dict = {
                    "nodes": [
                        {"id": node.id, "type": node.type} for node in result.nodes
                    ],
                    "edges": [
                        {
                            "source": edge.source,
                            "target": edge.target,
                            "weight": edge.weight,
                        }
                        for edge in result.edges
                    ],
                    "clusters": result.clusters,
                    "days_analyzed": days,
                }

                print(json.dumps(result_dict, indent=2))
            else:
                # Rich text output for dependency graph
                title_parts = ["\n[bold blue]Test Dependency Insights"]
                if sut:
                    title_parts.append(f" for [yellow]{sut}[/yellow]")
                title_parts.append(f" (Last {days} days)\n")
                console.print("".join(title_parts))

                if result.nodes and result.edges:
                    # Show clusters
                    console.print("[bold]Test Clusters:[/bold]")
                    for i, cluster in enumerate(result.clusters[:5], 1):
                        console.print(f"  Cluster {i}: {len(cluster)} tests")

                    if len(result.clusters) > 5:
                        console.print(
                            f"  ... and {len(result.clusters) - 5} more clusters"
                        )

                    # Show high-impact nodes
                    console.print("\n[bold]High-Impact Components:[/bold]")
                    high_impact = sorted(
                        result.nodes,
                        key=lambda n: sum(
                            e.weight
                            for e in result.edges
                            if e.source == n.id or e.target == n.id
                        ),
                        reverse=True,
                    )
                    for node in high_impact[:5]:
                        console.print(f"  - {node.id} ({node.type})")

                    # Recommendations
                    console.print("\n[bold]Dependency Analysis Recommendations:[/bold]")
                    console.print(
                        "  - Consider refactoring highly connected components to reduce coupling"
                    )
                    console.print(
                        "  - Look for opportunities to parallelize isolated test clusters"
                    )
                else:
                    console.print(
                        "[yellow]Insufficient data for dependency analysis.[/yellow]"
                    )

        else:
            console.print(
                f"[bold red]Error:[/bold red] Unknown insight type: {insight_type}"
            )
            console.print(
                "Available insight types: summary, patterns, trends, dependencies"
            )

    except Exception as e:
        if format == OutputFormat.JSON:
            import json

            print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")
            console.print(traceback.format_exc(), style="red")


if __name__ == "__main__":
    app()
