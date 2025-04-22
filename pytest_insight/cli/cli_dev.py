"""Developer CLI functionality for pytest-insight."""

import inspect
import os
import traceback
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pytest_insight.core.config import load_config
from pytest_insight.core.core_api import (
    InsightAPI,
    Query,
)
from pytest_insight.core.core_api import analyze as core_analyze
from pytest_insight.core.core_api import compare as core_compare
from pytest_insight.core.core_api import get_insights as core_get_insights
from pytest_insight.core.core_api import get_predictive as core_get_predictive
from pytest_insight.core.core_api import query as core_query
from pytest_insight.core.query import Query as QueryClass
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
    "query": QueryClass,
    "analysis": core_analyze,
    "comparison": core_compare,
    "insights": core_get_insights,
    "predictive": core_get_predictive,
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
                            "default": (param.default if param.default is not inspect.Parameter.empty else None),
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

    console.print("[yellow]This method is currently stubbed and not fully implemented.[/yellow]")
    return None


def _create_method_command(class_name: str, method_name: str, method_info: Dict[str, Any]) -> Callable:
    """Create a command function for a specific API method."""

    def command_function(**kwargs):
        """Dynamic command function for API methods."""
        console = Console()
        console.print(f"Executing {class_name.capitalize()}.{method_name}...", style="blue")

        # Execute the appropriate method
        if class_name == "query":
            result = _execute_query_method(method_name, **kwargs)
        else:
            result = _execute_stub_method(class_name, method_name, **kwargs)

        if result is not None:
            _format_rich_output(result, title=f"Result of {class_name.capitalize()}.{method_name}")

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
    console.print("[bold green]Starting interactive pytest-insight shell...[/bold green]")
    console.print("Type 'help' for a list of commands, 'exit' or 'quit' to exit.")

    # Set up the prompt session with history
    history_file = os.path.expanduser("~/.insight_history")
    history = FileHistory(history_file) if os.path.exists(os.path.dirname(history_file)) else FileHistory()

    # Create a prompt session with minimal styling to avoid compatibility issues
    style = Style.from_dict(
        {
            # You can add minimal styling here if needed
            "prompt": "#00aa00",
        }
    )

    prompt_session = PromptSession(history=history, style=style)

    # Set up console for rich output
    console = Console()

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
        "Analysis": core_analyze,
        "Comparison": core_compare,
        "Insights": core_get_insights,
        "PredictiveAnalytics": core_get_predictive,
        # Make core API functions available
        "query": core_query,
        "compare": core_compare,
        "analyze": core_analyze,
        "get_insights": core_get_insights,
        "get_predictive": core_get_predictive,
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
        "api predictive",
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
    completer = WordCompleter(commands, ignore_case=True)

    prompt_session = PromptSession(history=history, completer=completer, style=style)

    # Main loop
    while True:
        try:
            # Get user input with current profile in prompt
            user_input = prompt_session.prompt(f"\n[pytest-insight:{context['active_profile']}] > ")

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
                console.print("    debug on/off/status   - Enable/disable/check debug mode")
                console.print("    python EXPRESSION     - Execute a Python expression in the shell context")

                console.print("\n  [bold cyan]Core API Access:[/bold cyan]")
                console.print("    api help              - Show help for working with core API classes directly")
                console.print("    api query             - Create a new Query instance using the core API")
                console.print("    api compare           - Create a new Comparison instance using the core API")
                console.print("    api analyze           - Create a new Analysis instance using the core API")
                console.print("    api insights          - Create a new Insights instance using the core API")
                console.print(
                    "    api predictive        - Create a new PredictiveAnalytics instance using the core API"
                )
                console.print("    api exec              - Execute a method on a core API object")

                console.print("\n  [bold cyan]Profile Management:[/bold cyan]")
                console.print("    profile list          - List all available profiles")
                console.print("    profile create NAME   - Create a new profile")
                console.print("    profile switch NAME   - Switch to a different profile")
                console.print("    profile active        - Show the active profile")

                console.print("\n  [bold cyan]Query Management:[/bold cyan]")
                console.print("    query new             - Start a new query")
                console.print("    query list            - List saved queries")
                console.print("    query show NAME       - Show a saved query")
                console.print("    query save NAME       - Save the current query")
                console.print("    query load NAME       - Load a saved query")
                console.print("    query execute         - Execute the current query")
                console.print("    query filter_by_test  - Start building test-level filters")
                console.print("    query test_filter TYPE VALUE - Add a test filter (when in test filter mode)")
                console.print("    query apply_test_filter - Apply test filters and return to query context")

                console.print("\n  [bold cyan]Filtering (Detailed):[/bold cyan]")
                console.print("    query filter_by_test  - Start building test-level filters")
                console.print("    query test_filter TYPE VALUE - Add a test filter (when in test filter mode)")
                console.print("    query apply_test_filter - Apply test filters and return to query context")

                console.print("\n  [bold cyan]Filtering (Streamlined):[/bold cyan]")
                console.print("    query filter TYPE VALUE - Add a session-level filter (e.g., days, sut, outcome)")
                console.print("    query test TYPE VALUE   - Add a test-level filter (automatically applies)")
                console.print("    query chain FILTER1:VALUE1 FILTER2:VALUE2 ... - Create a complete query in one line")
                console.print("      Example: query chain days:7 sut:myapp test:outcome:failed test:duration_gt:5")

                console.print("\n  [bold cyan]Result Management:[/bold cyan]")
                console.print("    result list           - List saved results")
                console.print("    result show NAME      - Show a saved result")
                console.print("    result save NAME      - Save the current result")
                console.print("    result compare NAME1 NAME2 - Compare two results")

                console.print("\n  [bold cyan]Session Management:[/bold cyan]")
                console.print("    session list          - List sessions in current result")
                console.print("    session show ID       - Show details of a session")
                console.print("    session tests ID      - List tests in a session")
                console.print("    session failures ID   - List failed tests in a session")
                continue

            # History command
            if user_input.lower() == "history":
                table = Table(title="Command History")
                table.add_column("#")
                table.add_column("Command")
                table.add_column("Result")

                for i, item in enumerate(context["history"][:-1]):  # Skip current command
                    result_summary = "N/A"
                    if item["result"]:
                        if isinstance(item["result"], dict) and "summary" in item["result"]:
                            result_summary = item["result"]["summary"]
                        else:
                            result_summary = (
                                str(item["result"])[:50] + "..."
                                if len(str(item["result"])) > 50
                                else str(item["result"])
                            )

                    table.add_row(str(i), item["command"], result_summary)

                console.print(table)
                context["history"][history_index]["result"] = {"summary": "Showed command history"}
                continue

            # Clear command
            if user_input.lower() == "clear":
                console.clear()
                context["history"][history_index]["result"] = {"action": "cleared screen"}
                continue

            # Debug command
            elif user_input.lower().startswith("debug"):
                parts = user_input.lower().split()
                if len(parts) < 2:
                    console.print("[bold red]Error:[/bold red] Debug command requires an argument (on, off, or status)")
                    context["history"][history_index]["result"] = {"error": "Missing debug argument"}
                    continue

                debug_action = parts[1]
                if debug_action == "on":
                    context["debug_mode"] = True
                    console.print("[bold green]Debug mode enabled[/bold green]")
                    context["history"][history_index]["result"] = {"action": "debug mode enabled"}
                elif debug_action == "off":
                    context["debug_mode"] = False
                    console.print("[bold yellow]Debug mode disabled[/bold yellow]")
                    context["history"][history_index]["result"] = {"action": "debug mode disabled"}
                elif debug_action == "status":
                    status = "enabled" if context["debug_mode"] else "disabled"
                    console.print(f"[bold blue]Debug mode is currently {status}[/bold blue]")
                    context["history"][history_index]["result"] = {"status": f"debug mode {status}"}
                else:
                    console.print("[bold red]Error:[/bold red] Invalid debug argument. Use 'on', 'off', or 'status'")
                    context["history"][history_index]["result"] = {"error": "Invalid debug argument"}
                continue

            # Query chain command - show current query chain
            elif user_input.lower() == "query chain" or user_input.lower() == "query.chain":
                if context["current_query"] is None:
                    console.print("[bold red]Error:[/bold red] No active query")
                    context["history"][history_index]["result"] = {"error": "No active query"}
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
                    console.print("[bold blue]DEBUG: Query Object Details:[/bold blue]")

                    # Show all attributes of the query object
                    for attr_name in dir(query_obj):
                        # Skip private attributes and methods
                        if attr_name.startswith("_") and attr_name != "_profile_name" and attr_name != "_filters":
                            continue

                        # Skip methods
                        attr = getattr(query_obj, attr_name)
                        if callable(attr):
                            continue

                        # Display the attribute
                        console.print(f"[blue]{attr_name}: {repr(attr)}[/blue]")

                    # Show equivalent Python code
                    console.print("\n[bold blue]DEBUG: Equivalent Python Code:[/bold blue]")
                    console.print("[blue]from pytest_insight.core.query import Query[/blue]")
                    console.print(f"[blue]query = {chain_str}[/blue]")
                    console.print("[blue]result = query.execute()[/blue]")

                context["history"][history_index]["result"] = {"query_chain": chain}
                continue

            # Handle dot notation for query methods (e.g., query.with_profile default)
            elif user_input.lower().startswith("query."):
                parts = user_input.lower().split(".", 1)
                if len(parts) < 2:
                    console.print("[bold red]Error:[/bold red] Invalid query command format")
                    context["history"][history_index]["result"] = {"error": "Invalid query command format"}
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
                    console.print("[bold blue]DEBUG: Executing Python API call:[/bold blue]")
                    arg_display = ", ".join([repr(a) for a in args])
                    api_call = f"Query.{method_name}({arg_display})"
                    console.print(f"[blue]{api_call}[/blue]")

                # Get the method from the Query class
                if method_name == "chain":
                    # Special handling for chain command
                    if context["current_query"] is None:
                        console.print("[bold red]Error:[/bold red] No active query")
                        context["history"][history_index]["result"] = {"error": "No active query"}
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
                        console.print("\n[bold blue]DEBUG: Query Object Details:[/bold blue]")

                        # Show all attributes of the query object
                        for attr_name in dir(query_obj):
                            # Skip private attributes and methods
                            if attr_name.startswith("_") and attr_name != "_profile_name" and attr_name != "_filters":
                                continue

                            # Skip methods
                            attr = getattr(query_obj, attr_name)
                            if callable(attr):
                                continue

                            # Display the attribute
                            console.print(f"[blue]{attr_name}: {repr(attr)}[/blue]")

                        # Show equivalent Python code
                        console.print("\n[bold blue]DEBUG: Equivalent Python Code:[/bold blue]")
                        console.print("[blue]from pytest_insight.core.query import Query[/blue]")
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
                            session_count = len(result.sessions) if hasattr(result, "sessions") else 0
                            console.print("[bold green]Query executed successfully.[/bold green]")
                            console.print(f"Found {session_count} sessions.")

                            # Create a table to display the sessions
                            table = Table(title="Query Results")
                            table.add_column("Session ID")
                            table.add_column("SUT")
                            table.add_column("Start Time")
                            table.add_column("Duration (s)")
                            table.add_column("Tests")

                            for session in result.sessions[:10]:  # Limit to 10 sessions for display
                                table.add_row(
                                    session.session_id,
                                    session.sut_name,
                                    str(session.session_start_time),
                                    str(round(session.session_duration, 2)),
                                    str(len(session.test_results)),
                                )

                            console.print(table)

                            if len(result.sessions) > 10:
                                console.print(f"Showing 10 of {len(result.sessions)} sessions.")
                        else:
                            # For other methods, update the query object
                            result = method(context["current_query"], *args)

                            # If the method returns a new Query object, update current_query
                            if isinstance(result, Query):
                                context["current_query"] = result
                                console.print(f"[bold green]Applied {method_name}[/bold green]")
                            else:
                                console.print(
                                    f"[bold yellow]Warning: {method_name} did not return a Query object[/bold yellow]"
                                )

                            context["history"][history_index]["result"] = {
                                "action": f"applied {method_name}",
                                "args": args,
                            }
                    except Exception as e:
                        console.print(f"[bold red]Error executing {method_name}:[/bold red] {str(e)}")
                        console.print(traceback.format_exc(), style="red")
                        context["history"][history_index]["result"] = {"error": str(e)}
                else:
                    console.print(f"[bold red]Error:[/bold red] Unknown query method: {method_name}")
                    context["history"][history_index]["result"] = {"error": f"Unknown query method: {method_name}"}

                continue

            # Parse command
            parts = user_input.split()
            if not parts:
                continue

            command = parts[0].lower()

            # Profile management commands
            if command == "profile":
                if len(parts) < 2:
                    console.print("[bold red]Error:[/bold red] Missing profile subcommand")
                    context["history"][history_index]["result"] = {"error": "Missing profile subcommand"}
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
                    context["history"][history_index]["result"] = {"summary": f"Listed {len(profiles)} profiles"}

                elif subcommand == "create":
                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing profile name")
                        context["history"][history_index]["result"] = {"error": "Missing profile name"}
                        continue

                    name = parts[2]
                    console.print(f"Created profile [bold]{name}[/bold]")
                    context["history"][history_index]["result"] = {"summary": f"Created profile {name}"}

                elif subcommand == "switch":
                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing profile name")
                        context["history"][history_index]["result"] = {"error": "Missing profile name"}
                        continue

                    name = parts[2]
                    context["active_profile"] = name
                    console.print(f"Switched to profile [bold]{name}[/bold]")
                    context["history"][history_index]["result"] = {"summary": f"Switched to profile {name}"}

                elif subcommand == "active":
                    console.print(f"Active profile: [bold]{context['active_profile']}[/bold]")
                    context["history"][history_index]["result"] = {
                        "summary": f"Active profile: {context['active_profile']}"
                    }

                else:
                    console.print(f"[bold red]Error:[/bold red] Unknown profile subcommand: {subcommand}")
                    context["history"][history_index]["result"] = {"error": f"Unknown profile subcommand: {subcommand}"}

            # Query commands
            elif command == "query":
                if len(parts) < 2:
                    console.print("[bold red]Error:[/bold red] Missing query subcommand")
                    context["history"][history_index]["result"] = {"error": "Missing query subcommand"}
                    continue

                subcommand = parts[1].lower()

                if subcommand == "new":
                    context["current_query"] = Query()
                    console.print("Created a new query")
                    context["history"][history_index]["result"] = {"summary": "Created new query"}

                elif subcommand == "list":
                    if not context["queries"]:
                        console.print("No saved queries")
                        context["history"][history_index]["result"] = {"summary": "No saved queries"}
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
                        context["history"][history_index]["result"] = {"error": "Missing query name"}
                        continue

                    name = parts[2]
                    if name not in context["queries"]:
                        console.print(f"[bold red]Error:[/bold red] Query '{name}' not found")
                        context["history"][history_index]["result"] = {"error": f"Query '{name}' not found"}
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
                        console.print("[bold red]Error:[/bold red] No active query to save")
                        context["history"][history_index]["result"] = {"error": "No active query to save"}
                        continue

                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing query name")
                        context["history"][history_index]["result"] = {"error": "Missing query name"}
                        continue

                    name = parts[2]
                    context["queries"][name] = context["current_query"]
                    console.print(f"Saved query as [bold]{name}[/bold]")
                    context["history"][history_index]["result"] = {"summary": f"Saved query as {name}"}

                elif subcommand == "load":
                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing query name")
                        context["history"][history_index]["result"] = {"error": "Missing query name"}
                        continue

                    name = parts[2]
                    if name not in context["queries"]:
                        console.print(f"[bold red]Error:[/bold red] Query '{name}' not found")
                        context["history"][history_index]["result"] = {"error": f"Query '{name}' not found"}
                        continue

                    context["current_query"] = context["queries"][name]
                    console.print(f"Loaded query [bold]{name}[/bold]")
                    context["history"][history_index]["result"] = {"summary": f"Loaded query {name}"}

                elif subcommand == "execute":
                    if not context["current_query"]:
                        console.print("[bold red]Error:[/bold red] No active query to execute")
                        context["history"][history_index]["result"] = {"error": "No active query to execute"}
                        continue

                    try:
                        result = context["current_query"].execute()
                        context["current_result"] = result

                        console.print(f"Query executed successfully. Found {len(result.sessions)} sessions.")
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

                            for session in result.sessions[:10]:  # Limit to 10 sessions for display
                                table.add_row(
                                    session.session_id,
                                    session.sut_name,
                                    str(session.session_start_time),
                                    str(round(session.session_duration, 2)),
                                    str(len(session.test_results)),
                                )

                            console.print(table)

                            if len(result.sessions) > 10:
                                console.print(f"Showing 10 of {len(result.sessions)} sessions.")
                    except Exception as e:
                        console.print(f"[bold red]Error:[/bold red] {str(e)}")
                        console.print(traceback.format_exc(), style="red")
                        context["history"][history_index]["result"] = {"error": str(e)}

                elif subcommand == "filter_by_test":
                    if not context["current_query"]:
                        console.print("[bold red]Error:[/bold red] No active query. Use 'query new' first.")
                        context["history"][history_index]["result"] = {"error": "No active query to filter"}
                        continue

                    # Enter test filter mode
                    context["in_test_filter"] = True
                    context["test_filter_builder"] = context["current_query"].filter_by_test()
                    console.print(
                        "[bold green]Entered test filter mode.[/bold green] Use 'query test_filter TYPE VALUE' to add filters and 'query apply_test_filter' when done."
                    )
                    context["history"][history_index]["result"] = {"summary": "Entered test filter mode"}

                elif subcommand == "test_filter":
                    if not context["in_test_filter"] or not context["test_filter_builder"]:
                        console.print(
                            "[bold red]Error:[/bold red] Not in test filter mode. Use 'query filter_by_test' first."
                        )
                        context["history"][history_index]["result"] = {"error": "Not in test filter mode"}
                        continue

                    if len(parts) < 4:
                        console.print("[bold red]Error:[/bold red] Missing filter type or value")
                        context["history"][history_index]["result"] = {"error": "Missing filter type or value"}
                        continue

                    filter_type = parts[2].lower()
                    filter_value = " ".join(parts[3:])

                    try:
                        builder = context["test_filter_builder"]

                        if filter_type == "outcome":
                            builder = builder.with_outcome(filter_value)
                        elif filter_type == "duration_gt":
                            builder = builder.with_duration_greater_than(float(filter_value))
                        elif filter_type == "duration_lt":
                            builder = builder.with_duration_less_than(float(filter_value))
                        elif filter_type == "nodeid":
                            builder = builder.with_nodeid_pattern(filter_value)
                        elif filter_type == "name":
                            builder = builder.with_name_pattern(filter_value)
                        else:
                            console.print(f"[bold red]Error:[/bold red] Unknown test filter type: {filter_type}")
                            context["history"][history_index]["result"] = {
                                "error": f"Unknown test filter type: {filter_type}"
                            }
                            continue

                        context["test_filter_builder"] = builder
                        console.print(f"Added test filter: {filter_type} = {filter_value}")
                        context["history"][history_index]["result"] = {
                            "summary": f"Added test filter: {filter_type} = {filter_value}"
                        }
                    except Exception as e:
                        console.print(f"[bold red]Error:[/bold red] {str(e)}")
                        console.print(traceback.format_exc(), style="red")
                        context["history"][history_index]["result"] = {"error": str(e)}

                elif subcommand == "apply_test_filter":
                    if not context["in_test_filter"] or not context["test_filter_builder"]:
                        console.print(
                            "[bold red]Error:[/bold red] Not in test filter mode. Use 'query filter_by_test' first."
                        )
                        context["history"][history_index]["result"] = {"error": "Not in test filter mode"}
                        continue

                    try:
                        # Apply the test filters and return to query context
                        context["current_query"] = context["test_filter_builder"].apply()
                        context["in_test_filter"] = False
                        context["test_filter_builder"] = None
                        console.print("[bold green]Applied test filters.[/bold green] Returned to query context.")
                        context["history"][history_index]["result"] = {"summary": "Applied test filters"}
                    except Exception as e:
                        console.print(f"[bold red]Error:[/bold red] {str(e)}")
                        console.print(traceback.format_exc(), style="red")
                        context["history"][history_index]["result"] = {"error": str(e)}

                elif subcommand == "filter":
                    if not context["current_query"]:
                        console.print("[bold red]Error:[/bold red] No active query. Use 'query new' first.")
                        context["history"][history_index]["result"] = {"error": "No active query to filter"}
                        continue

                    if len(parts) < 4:
                        console.print("[bold red]Error:[/bold red] Missing filter type or value")
                        context["history"][history_index]["result"] = {"error": "Missing filter type or value"}
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
                            console.print(f"[bold red]Error:[/bold red] Unknown filter type: {filter_type}")
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
                        console.print("[bold red]Error:[/bold red] No active query. Use 'query new' first.")
                        context["history"][history_index]["result"] = {"error": "No active query to filter"}
                        continue

                    if len(parts) < 4:
                        console.print("[bold red]Error:[/bold red] Missing filter type or value")
                        context["history"][history_index]["result"] = {"error": "Missing filter type or value"}
                        continue

                    filter_type = parts[2].lower()
                    filter_value = " ".join(parts[3:])

                    try:
                        # Create a test filter builder if not already in test mode
                        if not context["in_test_filter"]:
                            context["in_test_filter"] = True
                            context["test_filter_builder"] = context["current_query"].filter_by_test()

                        builder = context["test_filter_builder"]

                        if filter_type == "outcome":
                            builder = builder.with_outcome(filter_value)
                        elif filter_type == "duration_gt":
                            builder = builder.with_duration_greater_than(float(filter_value))
                        elif filter_type == "duration_lt":
                            builder = builder.with_duration_less_than(float(filter_value))
                        elif filter_type == "nodeid":
                            builder = builder.with_nodeid_pattern(filter_value)
                        elif filter_type == "name":
                            builder = builder.with_name_pattern(filter_value)
                        else:
                            console.print(f"[bold red]Error:[/bold red] Unknown test filter type: {filter_type}")
                            context["history"][history_index]["result"] = {
                                "error": f"Unknown test filter type: {filter_type}"
                            }
                            continue

                        context["test_filter_builder"] = builder

                        # Automatically apply the test filter
                        context["current_query"] = builder.apply()
                        context["in_test_filter"] = False
                        context["test_filter_builder"] = None

                        console.print(f"Added and applied test filter: {filter_type} = {filter_value}")
                        context["history"][history_index]["result"] = {
                            "summary": f"Added and applied test filter: {filter_type} = {filter_value}"
                        }
                    except Exception as e:
                        console.print(f"[bold red]Error:[/bold red] {str(e)}")
                        console.print(traceback.format_exc(), style="red")
                        context["history"][history_index]["result"] = {"error": str(e)}

                elif subcommand == "chain":
                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing filter specifications")
                        context["history"][history_index]["result"] = {"error": "Missing filter specifications"}
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
                                raise ValueError(f"Invalid filter specification: {spec}. Format should be type:value")

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
                                    test_filter_builder = test_filter_builder.with_outcome(filter_value)
                                elif test_filter_type == "duration_gt":
                                    test_filter_builder = test_filter_builder.with_duration_greater_than(
                                        float(filter_value)
                                    )
                                elif test_filter_type == "duration_lt":
                                    test_filter_builder = test_filter_builder.with_duration_less_than(
                                        float(filter_value)
                                    )
                                elif test_filter_type == "nodeid":
                                    test_filter_builder = test_filter_builder.with_nodeid_pattern(filter_value)
                                elif test_filter_type == "name":
                                    test_filter_builder = test_filter_builder.with_name_pattern(filter_value)
                                else:
                                    raise ValueError(f"Unknown test filter type: {test_filter_type}")

                                applied_filters.append(f"test:{test_filter_type}:{filter_value}")
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
                                    raise ValueError(f"Unknown filter type: {filter_type}")

                                applied_filters.append(f"{filter_type}:{filter_value}")

                        # If we're still in test filter mode, apply those filters
                        if in_test_filter:
                            query = test_filter_builder.apply()

                        # Store the query
                        context["current_query"] = query

                        # Show summary
                        console.print("[bold green]Created query with filters:[/bold green]")
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
                    console.print("[bold red]Error:[/bold red] Missing result subcommand")
                    context["history"][history_index]["result"] = {"error": "Missing result subcommand"}
                    continue

                subcommand = parts[1].lower()

                if subcommand == "list":
                    if not context["results"]:
                        console.print("No saved results")
                        context["history"][history_index]["result"] = {"summary": "No saved results"}
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
                        context["history"][history_index]["result"] = {"error": "Missing result name"}
                        continue

                    name = parts[2]
                    if name not in context["results"]:
                        console.print(f"[bold red]Error:[/bold red] Result '{name}' not found")
                        context["history"][history_index]["result"] = {"error": f"Result '{name}' not found"}
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

                        for session in result.sessions[:10]:  # Limit to 10 sessions for display
                            table.add_row(
                                session.session_id,
                                session.sut_name,
                                str(session.session_start_time),
                                str(round(session.session_duration, 2)),
                                str(len(session.test_results)),
                            )

                        console.print(table)

                        if len(result.sessions) > 10:
                            console.print(f"Showing 10 of {len(result.sessions)} sessions.")
                    context["history"][history_index]["result"] = {"summary": f"Showed result {name}"}

                elif subcommand == "save":
                    if not context["current_result"]:
                        console.print("[bold red]Error:[/bold red] No active result to save")
                        context["history"][history_index]["result"] = {"error": "No active result to save"}
                        continue

                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing result name")
                        context["history"][history_index]["result"] = {"error": "Missing result name"}
                        continue

                    name = parts[2]
                    context["results"][name] = context["current_result"]
                    console.print(f"Saved result as [bold]{name}[/bold]")
                    context["history"][history_index]["result"] = {"summary": f"Saved result as {name}"}

                elif subcommand == "compare":
                    if len(parts) < 4:
                        console.print("[bold red]Error:[/bold red] Missing result names to compare")
                        context["history"][history_index]["result"] = {"error": "Missing result names to compare"}
                        continue

                    name1 = parts[2]
                    name2 = parts[3]

                    if name1 not in context["results"]:
                        console.print(f"[bold red]Error:[/bold red] Result '{name1}' not found")
                        context["history"][history_index]["result"] = {"error": f"Result '{name1}' not found"}
                        continue

                    if name2 not in context["results"]:
                        console.print(f"[bold red]Error:[/bold red] Result '{name2}' not found")
                        context["history"][history_index]["result"] = {"error": f"Result '{name2}' not found"}
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
                    context["history"][history_index]["result"] = {"summary": f"Compared results {name1} and {name2}"}

                else:
                    console.print(f"[bold red]Error:[/bold red] Unknown result subcommand: {subcommand}")
                    context["history"][history_index]["result"] = {"error": f"Unknown result subcommand: {subcommand}"}

            # Session commands
            elif user_input.lower().startswith("session."):
                if context["current_result"] is None:
                    console.print("[bold red]Error:[/bold red] No query results available. Execute a query first.")
                    context["history"][history_index]["result"] = {"error": "No query results"}
                    continue

                parts = user_input.split(".", 1)
                if len(parts) < 2:
                    console.print("[bold red]Error:[/bold red] Invalid session command format")
                    context["history"][history_index]["result"] = {"error": "Invalid session command format"}
                    continue

                subcommand = parts[1].strip()

                # Show debug information if debug mode is enabled
                if context["debug_mode"]:
                    console.print("[bold blue]DEBUG: Executing session operation:[/bold blue]")
                    if hasattr(context["current_result"], "sessions"):
                        session_count = len(context["current_result"].sessions)
                        console.print(f"[blue]# Processing QueryResult with {session_count} sessions[/blue]")
                        console.print(f"[blue]# Operation: {subcommand}[/blue]")

                if subcommand == "list":
                    if not context["current_result"] or not context["current_result"].sessions:
                        console.print("[bold red]Error:[/bold red] No active result with sessions")
                        context["history"][history_index]["result"] = {"error": "No active result with sessions"}
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
                    if not context["current_result"] or not context["current_result"].sessions:
                        console.print("[bold red]Error:[/bold red] No active result with sessions")
                        context["history"][history_index]["result"] = {"error": "No active result with sessions"}
                        continue

                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing session ID")
                        context["history"][history_index]["result"] = {"error": "Missing session ID"}
                        continue

                    session_id = parts[2]
                    session = next(
                        (s for s in context["current_result"].sessions if s.id == session_id),
                        None,
                    )

                    if not session:
                        console.print(f"[bold red]Error:[/bold red] Session '{session_id}' not found")
                        context["history"][history_index]["result"] = {"error": f"Session '{session_id}' not found"}
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

                    context["history"][history_index]["result"] = {"summary": f"Showed session {session_id}"}

                elif subcommand == "tests":
                    if not context["current_result"] or not context["current_result"].sessions:
                        console.print("[bold red]Error:[/bold red] No active result with sessions")
                        context["history"][history_index]["result"] = {"error": "No active result with sessions"}
                        continue

                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing session ID")
                        context["history"][history_index]["result"] = {"error": "Missing session ID"}
                        continue

                    session_id = parts[2]
                    session = next(
                        (s for s in context["current_result"].sessions if s.id == session_id),
                        None,
                    )

                    if not session:
                        console.print(f"[bold red]Error:[/bold red] Session '{session_id}' not found")
                        context["history"][history_index]["result"] = {"error": f"Session '{session_id}' not found"}
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
                            (str(round(test.duration, 3)) if test.duration is not None else "N/A"),
                        )

                    console.print(table)
                    context["history"][history_index]["result"] = {
                        "summary": f"Listed {len(session.test_results)} tests in session {session_id}"
                    }

                elif subcommand == "failures":
                    if not context["current_result"] or not context["current_result"].sessions:
                        console.print("[bold red]Error:[/bold red] No active result with sessions")
                        context["history"][history_index]["result"] = {"error": "No active result with sessions"}
                        continue

                    if len(parts) < 3:
                        console.print("[bold red]Error:[/bold red] Missing session ID")
                        context["history"][history_index]["result"] = {"error": "Missing session ID"}
                        continue

                    session_id = parts[2]
                    session = next(
                        (s for s in context["current_result"].sessions if s.id == session_id),
                        None,
                    )

                    if not session:
                        console.print(f"[bold red]Error:[/bold red] Session '{session_id}' not found")
                        context["history"][history_index]["result"] = {"error": f"Session '{session_id}' not found"}
                        continue

                    failures = [t for t in session.test_results if t.outcome == "failed"]

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
                            (str(round(test.duration, 3)) if test.duration is not None else "N/A"),
                        )

                    console.print(table)

                    # Show failure details
                    for i, test in enumerate(failures):
                        if hasattr(test, "longrepr") and test.longrepr:
                            console.print(f"\n[bold red]Failure {i+1}:[/bold red] {test.nodeid}")
                            console.print(test.longrepr)

                    context["history"][history_index]["result"] = {
                        "summary": f"Listed {len(failures)} failures in session {session_id}"
                    }

                else:
                    console.print(f"[bold red]Error:[/bold red] Unknown session subcommand: {subcommand}")
                    context["history"][history_index]["result"] = {"error": f"Unknown session subcommand: {subcommand}"}

            # Python command - execute Python code directly
            elif user_input.lower().startswith("python "):
                python_code = user_input[7:].strip()
                if not python_code:
                    console.print("[bold red]Error:[/bold red] Missing Python expression")
                    context["history"][history_index]["result"] = {"error": "Missing Python expression"}
                    continue

                try:
                    # Execute the Python code in the context of the shell
                    result = eval(python_code, globals(), context)

                    # Display the result
                    console.print("[bold green]Python expression executed:[/bold green]")

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
                    console.print(f"[bold red]Error executing Python expression:[/bold red] {str(e)}")
                    console.print(traceback.format_exc(), style="red")
                    context["history"][history_index]["result"] = {"error": str(e)}
                continue

            # API commands for direct core API access
            elif user_input.lower().startswith("api "):
                parts = user_input.lower().split(" ", 2)
                if len(parts) < 2:
                    console.print("[bold red]Error:[/bold red] Missing API subcommand")
                    context["history"][history_index]["result"] = {"error": "Missing API subcommand"}
                    continue

                subcommand = parts[1].lower()

                if subcommand == "help":
                    console.print("\n[bold]Core API Direct Access:[/bold]")
                    console.print(
                        "The interactive shell provides direct access to the pytest-insight core API classes."
                    )
                    console.print("You can use these classes directly in Python expressions or with the api commands.")

                    console.print("\n[bold cyan]Available Core Classes:[/bold cyan]")
                    console.print("  Query       - Find and filter test sessions")
                    console.print("  Analysis    - Analyze test results")
                    console.print("  Comparison  - Compare test results")
                    console.print("  Insights    - Generate comprehensive insights")
                    console.print("  PredictiveAnalytics - Generate predictive analytics")
                    console.print("  InsightAPI  - Unified API for all components")

                    console.print("\n[bold cyan]Using Core Classes with Python Commands:[/bold cyan]")
                    console.print("  python Query().with_profile('default').in_last_days(7).execute()")
                    console.print("  python InsightAPI().query().in_last_days(7).execute()")
                    console.print("  query('default').in_last_days(7).execute()")

                    console.print("\n[bold cyan]Using Core API Factory Functions:[/bold cyan]")
                    console.print("  python query()      - Create a new Query instance")
                    console.print("  python compare()    - Create a new Comparison instance")
                    console.print("  python analyze()    - Create a new Analysis instance")
                    console.print("  python get_insights() - Create a new Insights instance")
                    console.print("  python get_predictive() - Create a new PredictiveAnalytics instance")

                    console.print("\n[bold cyan]Direct Method Execution:[/bold cyan]")
                    console.print("  api exec query in_last_days 7    - Execute method on current query object")
                    console.print("  api exec analysis health_report  - Execute method on current analysis object")
                    console.print("  api exec comparison compare_suts my-app1 my-app2 - Execute with arguments")

                    context["history"][history_index]["result"] = {"action": "showed API help"}

                elif subcommand == "query":
                    # Create a new Query instance using the core API
                    profile_name = context["active_profile"]
                    if len(parts) > 2:
                        profile_name = parts[2]

                    result = core_query(profile_name)
                    context["current_query"] = result

                    console.print(f"[bold green]Created new Query instance with profile '{profile_name}'[/bold green]")
                    console.print("Use 'query chain' to see the current query chain")
                    console.print("Use 'python' commands to work with the query directly")

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
                    console.print("Use 'python' commands to work with the comparison directly")

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
                    console.print("Use 'python' commands to work with the analysis directly")

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
                    console.print("Use 'python' commands to work with the insights directly")

                    context["history"][history_index]["result"] = {
                        "action": "created Insights instance",
                        "profile": profile_name,
                    }

                elif subcommand == "predictive":
                    # Create a new PredictiveAnalytics instance using the core API
                    profile_name = context["active_profile"]
                    if len(parts) > 2:
                        profile_name = parts[2]

                    result = core_get_predictive(profile_name)
                    context["current_predictive"] = result

                    console.print(
                        f"[bold green]Created new PredictiveAnalytics instance with profile '{profile_name}'[/bold green]"
                    )
                    console.print("Use 'python' commands to work with the predictive analytics directly")

                    context["history"][history_index]["result"] = {
                        "action": "created PredictiveAnalytics instance",
                        "profile": profile_name,
                    }

                elif subcommand == "exec":
                    # Execute a method on a core API object
                    if len(parts) < 2:
                        console.print("[bold red]Error:[/bold red] Missing object and method specification")
                        console.print("Usage: api exec [object] [method] [args...]")
                        context["history"][history_index]["result"] = {
                            "error": "Missing object and method specification"
                        }
                        continue

                    # Parse the command: api exec [object] [method] [args...]
                    exec_parts = user_input.split(" ", 3)[2:]  # Skip 'api exec'

                    if len(exec_parts) < 2:
                        console.print("[bold red]Error:[/bold red] Missing object or method name")
                        console.print("Usage: api exec [object] [method] [args...]")
                        context["history"][history_index]["result"] = {"error": "Missing object or method name"}
                        continue

                    obj_name = exec_parts[0].lower()

                    # Extract method name and arguments
                    remaining_parts = (
                        exec_parts[1].split()
                        if len(exec_parts) == 2
                        else (exec_parts[1].split() + exec_parts[2].split() if len(exec_parts) > 2 else [])
                    )
                    if not remaining_parts:
                        console.print("[bold red]Error:[/bold red] Missing method name")
                        console.print("Usage: api exec [object] [method] [args...]")
                        context["history"][history_index]["result"] = {"error": "Missing method name"}
                        continue

                    method_name = remaining_parts[0]

                    # Parse arguments if any
                    args = []
                    if len(remaining_parts) > 1:
                        raw_args = remaining_parts[1:]

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
                            console.print("[bold red]Error:[/bold red] No active Query object")
                            console.print("Create one first with 'api query' or 'query new'")
                            context["history"][history_index]["result"] = {"error": "No active Query object"}
                            continue
                    elif obj_name == "analysis":
                        target_obj = context.get("current_analysis")
                        if target_obj is None:
                            console.print("[bold red]Error:[/bold red] No active Analysis object")
                            console.print("Create one first with 'api analyze'")
                            context["history"][history_index]["result"] = {"error": "No active Analysis object"}
                            continue
                    elif obj_name == "comparison":
                        target_obj = context.get("current_comparison")
                        if target_obj is None:
                            console.print("[bold red]Error:[/bold red] No active Comparison object")
                            console.print("Create one first with 'api compare'")
                            context["history"][history_index]["result"] = {"error": "No active Comparison object"}
                            continue
                    elif obj_name == "insights":
                        target_obj = context.get("current_insights")
                        if target_obj is None:
                            console.print("[bold red]Error:[/bold red] No active Insights object")
                            console.print("Create one first with 'api insights'")
                            context["history"][history_index]["result"] = {"error": "No active Insights object"}
                            continue
                    elif obj_name == "predictive":
                        target_obj = context.get("current_predictive")
                        if target_obj is None:
                            console.print("[bold red]Error:[/bold red] No active PredictiveAnalytics object")
                            console.print("Create one first with 'api predictive'")
                            context["history"][history_index]["result"] = {
                                "error": "No active PredictiveAnalytics object"
                            }
                            continue
                    else:
                        console.print(f"[bold red]Error:[/bold red] Unknown object type: {obj_name}")
                        console.print("Available objects: query, analysis, comparison, insights, predictive")
                        context["history"][history_index]["result"] = {"error": f"Unknown object type: {obj_name}"}
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

                        context["history"][history_index]["result"] = {"error": f"Method '{method_name}' not found"}
                        continue

                    # Get the method
                    method = getattr(target_obj, method_name)

                    # Show debug information if debug mode is enabled
                    if context["debug_mode"]:
                        console.print("[bold blue]DEBUG: Executing API method call:[/bold blue]")
                        arg_display = ", ".join([repr(a) for a in args])
                        api_call = f"{obj_name}.{method_name}({arg_display})"
                        console.print(f"[blue]{api_call}[/blue]")

                    try:
                        # Execute the method
                        result = method(*args)

                        # Handle the result
                        console.print(f"[bold green]Method {method_name} executed successfully[/bold green]")

                        # Store the result if it's a new object of a known type
                        if isinstance(result, Query):
                            context["current_query"] = result
                            console.print("Updated current query with the result")
                        elif isinstance(result, core_analyze):
                            context["current_analysis"] = result
                            console.print("Updated current analysis with the result")
                        elif isinstance(result, core_compare):
                            context["current_comparison"] = result
                            console.print("Updated current comparison with the result")
                        elif isinstance(result, core_get_insights):
                            context["current_insights"] = result
                            console.print("Updated current insights with the result")
                        elif isinstance(result, core_get_predictive):
                            context["current_predictive"] = result
                            console.print("Updated current predictive analytics with the result")

                        # Display the result
                        if result is not None:
                            if isinstance(result, (dict, list)):
                                _format_rich_output(result, title=f"Result of {method_name}")
                            else:
                                console.print(f"Result: {result}")

                        context["history"][history_index]["result"] = {
                            "action": f"executed {obj_name}.{method_name}",
                            "args": args,
                            "result_type": (type(result).__name__ if result is not None else "None"),
                        }
                    except Exception as e:
                        console.print(f"[bold red]Error executing {method_name}:[/bold red] {str(e)}")
                        console.print(traceback.format_exc(), style="red")
                        context["history"][history_index]["result"] = {"error": str(e)}

                else:
                    console.print(f"[bold red]Error:[/bold red] Unknown API subcommand: {subcommand}")
                    console.print("Available subcommands: help, query, compare, analyze, insights, predictive, exec")
                    context["history"][history_index]["result"] = {"error": f"Unknown API subcommand: {subcommand}"}

                continue

            # Debug command
            elif user_input.lower().startswith("debug"):
                parts = user_input.lower().split()
                if len(parts) < 2:
                    console.print("[bold red]Error:[/bold red] Debug command requires an argument (on, off, or status)")
                    context["history"][history_index]["result"] = {"error": "Missing debug argument"}
                    continue

                debug_action = parts[1]
                if debug_action == "on":
                    context["debug_mode"] = True
                    console.print("[bold green]Debug mode enabled[/bold green]")
                    context["history"][history_index]["result"] = {"action": "debug mode enabled"}
                elif debug_action == "off":
                    context["debug_mode"] = False
                    console.print("[bold yellow]Debug mode disabled[/bold yellow]")
                    context["history"][history_index]["result"] = {"action": "debug mode disabled"}
                elif debug_action == "status":
                    status = "enabled" if context["debug_mode"] else "disabled"
                    console.print(f"[bold blue]Debug mode is currently {status}[/bold blue]")
                    context["history"][history_index]["result"] = {"status": f"debug mode {status}"}
                else:
                    console.print("[bold red]Error:[/bold red] Invalid debug argument. Use 'on', 'off', or 'status'")
                    context["history"][history_index]["result"] = {"error": "Invalid debug argument"}
                continue

            # Unknown command
            else:
                console.print(f"[bold red]Error:[/bold red] Unknown command: {command}")
                context["history"][history_index]["result"] = {"error": f"Unknown command: {command}"}

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


@app.command("shell", help="Start an interactive shell for exploring the pytest-insight API")
def interactive_shell():
    """Start an interactive shell for exploring the pytest-insight API."""
    try:
        # Just check if prompt_toolkit is available
        import importlib.util

        if importlib.util.find_spec("prompt_toolkit") is None:
            raise ImportError("prompt_toolkit not found")
    except ImportError:
        console = Console()
        console.print("[bold red]Error:[/bold red] prompt_toolkit is required for the interactive shell.")
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
    test_pattern: Optional[str] = typer.Option(None, help="Test pattern (supports wildcards)"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
    format: OutputFormat = typer.Option(OutputFormat.TEXT, help="Output format (text or json)"),
):
    """Compare test results between two SUTs.

    This command performs a comparison between test results from two SUTs,
    identifying new failures, fixed tests, reliability_rate tests, and performance changes.
    """
    console = Console()

    try:
        # Load configuration
        from pytest_insight.core.config import load_config

        load_config()

        # Create comparison instance with optional profile
        from pytest_insight.core.comparison import comparison

        # Initialize comparison with profile if specified
        if profile:
            comp = comparison(base_profile=profile, target_profile=profile)
        else:
            comp = comparison()

        # Apply SUT filter
        comp = comp.between_suts(base_sut, target_sut)

        # Apply days filter if specified
        if days is not None:
            comp = comp.apply_to_both(lambda q: q.in_last_days(days))

        # Execute the comparison
        result = comp.execute()

        # Format and display results
        if format == OutputFormat.JSON:
            import json

            # Convert result to JSON-serializable dict
            result_dict = {
                "new_failures": result.new_failures,
                "new_passes": result.new_passes,
                "unreliable_tests": result.unreliable_tests,
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
                ", ".join(result.new_failures[:5]) + ("..." if len(result.new_failures) > 5 else ""),
            )
            table.add_row(
                "Fixed Tests",
                str(len(result.new_passes)),
                ", ".join(result.new_passes[:5]) + ("..." if len(result.new_passes) > 5 else ""),
            )
            table.add_row(
                "Reliability_rate Tests",
                str(len(result.unreliable_tests)),
                ", ".join(result.unreliable_tests[:5]) + ("..." if len(result.unreliable_tests) > 5 else ""),
            )
            table.add_row(
                "Slower Tests",
                str(len(result.slower_tests)),
                ", ".join(result.slower_tests[:5]) + ("..." if len(result.slower_tests) > 5 else ""),
            )
            table.add_row(
                "Faster Tests",
                str(len(result.faster_tests)),
                ", ".join(result.faster_tests[:5]) + ("..." if len(result.faster_tests) > 5 else ""),
            )
            table.add_row(
                "Missing Tests",
                str(len(result.missing_tests)),
                ", ".join(result.missing_tests[:5]) + ("..." if len(result.missing_tests) > 5 else ""),
            )
            table.add_row(
                "New Tests",
                str(len(result.new_tests)),
                ", ".join(result.new_tests[:5]) + ("..." if len(result.new_tests) > 5 else ""),
            )

            console.print(table)

            # Session information
            console.print("\n[bold]Session Information:[/bold]")
            console.print(f"  Base: [cyan]{result.base_session.sut}[/cyan] ({result.base_session.timestamp})")
            console.print(f"  Target: [cyan]{result.target_session.sut}[/cyan] ({result.target_session.timestamp})")

            # Provide guidance on next steps
            if result.has_changes():
                console.print("\n[bold green]Suggested Next Steps:[/bold green]")
                if result.new_failures:
                    console.print(
                        "  - [yellow]Low reliability detected.[/yellow] Run 'insight analyze --sut",
                        target_sut,
                    )
                if result.unreliable_tests:
                    console.print(
                        "  - [red]High failure rate detected.[/red] Run 'insight analyze --unreliable-only --sut",
                        target_sut,
                    )
            else:
                console.print("\n[bold green]No significant changes detected between the SUTs.[/bold green]")

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
    test_pattern: Optional[str] = typer.Option(None, help="Test pattern (supports wildcards)"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
    report_type: str = "health",  # Default to health report type
    unreliable_only: bool = typer.Option(False, help="Focus only on unreliable tests"),
    format: OutputFormat = typer.Option(OutputFormat.TEXT, help="Output format (text or json)"),
    config_file: Optional[str] = typer.Option(None, help="Path to configuration file"),
):
    """Analyze test results for a specific SUT.

    This command performs analysis on test results, providing insights into
    test health, stability, performance, and reliability.
    """
    console = Console()

    try:
        # Load configuration
        from pytest_insight.core.config import load_config

        # Fix the config_file parameter to handle typer.Option objects
        if isinstance(config_file, typer.models.OptionInfo):
            config_file = None

        config = load_config(config_file)

        # Create API instance
        api = InsightAPI()
        if profile:
            api = api.with_profile(profile)

        # Build query
        query = api.query()
        if sut:
            query = query.for_sut(sut)
        query = query.in_last_days(days)

        # Execute the query to get filtered sessions
        result = query.execute()

        # Create analyzer with filtered sessions
        analyzer = api.analyze()
        analyzer._sessions = result.sessions

        # Check if the requested report type is enabled in config
        report_enabled = True
        if config and "reports" in config and report_type in config["reports"]:
            report_config = config["reports"][report_type]
            if "enabled" in report_config:
                report_enabled = report_config["enabled"]

        if not report_enabled:
            console.print(f"[bold red]Error:[/bold red] Report type '{report_type}' is disabled in configuration.")
            return

        # Display active configuration for the selected report type
        if format == OutputFormat.TEXT and config and "reports" in config and report_type in config["reports"]:
            report_config = config["reports"][report_type]
            console.print("\n[bold blue]Active Configuration:[/bold blue]")

            # Create a table to display the configuration
            table = Table(title=f"{report_type.capitalize()} Report Configuration")
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="green")

            for key, value in report_config.items():
                if isinstance(value, list):
                    value_str = ", ".join(value)
                else:
                    value_str = str(value)
                table.add_row(key.replace("_", " ").title(), value_str)

            console.print(table)
            console.print()

        # Execute the appropriate analysis based on report type
        if report_type == "health":
            # Get metrics to include from configuration
            metrics_to_include = [
                "pass_rate",
                "failure_rate",
                "skip_rate",
                "error_rate",
                "reliability_index",
                "rerun_recovery_rate",
                "total_tests",
                "total_sessions",
            ]
            if (
                config
                and "reports" in config
                and "summary" in config["reports"]
                and "metrics" in config["reports"]["summary"]
            ):
                metrics_to_include = config["reports"]["summary"]["metrics"]

            # Get sections to include from configuration
            sections_to_include = [
                "top_failures",
                "top_unreliable",
                "performance_issues",
            ]
            if (
                config
                and "reports" in config
                and "summary" in config["reports"]
                and "sections" in config["reports"]["summary"]
            ):
                sections_to_include = config["reports"]["summary"]["sections"]

            # Generate health report
            result = analyzer.health_report()

            if format == OutputFormat.JSON:
                import json

                # Convert result to JSON-serializable dict
                result_dict = {
                    "days_analyzed": days,
                }

                # Add metrics based on configuration
                if "pass_rate" in metrics_to_include:
                    result_dict["pass_rate"] = result.pass_rate
                if "failure_rate" in metrics_to_include:
                    result_dict["failure_rate"] = result.failure_rate
                if "skip_rate" in metrics_to_include:
                    result_dict["skip_rate"] = result.skip_rate
                if "error_rate" in metrics_to_include:
                    result_dict["error_rate"] = result.error_rate
                if "test_count" in metrics_to_include:
                    result_dict["total_tests"] = result.total_tests
                if "session_count" in metrics_to_include:
                    result_dict["total_sessions"] = result.total_sessions
                if "reliability_index" in metrics_to_include:
                    result_dict["reliability_index"] = (
                        result.reliability_metrics["reliability_index"] if hasattr(result, "reliability_metrics") else 0
                    )
                if "rerun_recovery_rate" in metrics_to_include:
                    result_dict["rerun_recovery_rate"] = (
                        result.reliability_metrics["rerun_recovery_rate"]
                        if hasattr(result, "reliability_metrics")
                        else 0
                    )

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

                # Add rows for each metric based on configuration
                metric_mapping = {
                    "pass_rate": (
                        "Pass Rate",
                        lambda r: f"{r['session_metrics'].get('pass_rate', 0):.1%}",
                    ),
                    "failure_rate": (
                        "Failure Rate",
                        lambda r: f"{r['session_metrics'].get('failure_rate', 0):.1%}",
                    ),
                    "skip_rate": (
                        "Skip Rate",
                        lambda r: f"{r['session_metrics'].get('skip_rate', 0):.1%}",
                    ),
                    "error_rate": (
                        "Error Rate",
                        lambda r: f"{r['session_metrics'].get('error_rate', 0):.1%}",
                    ),
                    "reliability_index": (
                        "Reliability Index",
                        lambda r: (
                            f"{r['reliability_metrics'].get('reliability_index', 100):.2f}"
                            if "reliability_metrics" in r
                            else "N/A"
                        ),
                    ),
                    "rerun_recovery_rate": (
                        "Rerun Recovery Rate",
                        lambda r: (
                            f"{r['reliability_metrics'].get('rerun_recovery_rate', 100):.1f}%"
                            if "reliability_metrics" in r
                            else "N/A"
                        ),
                    ),
                    "test_count": (
                        "Total Tests",
                        lambda r: str(r["session_metrics"].get("total_tests", 0)),
                    ),
                    "session_count": (
                        "Total Sessions",
                        lambda r: str(r["session_metrics"].get("total_sessions", 0)),
                    ),
                }

                for metric in metrics_to_include:
                    if metric in metric_mapping:
                        display_name, value_func = metric_mapping[metric]
                        table.add_row(display_name, value_func(result))

                console.print(table)

                # Add sections based on configuration
                if "top_failures" in sections_to_include and hasattr(result, "top_failures") and result.top_failures:
                    console.print("\n[bold red]Top Failing Tests:[/bold red]")
                    failure_table = Table(show_header=True, header_style="bold red")
                    failure_table.add_column("Test", style="cyan")
                    failure_table.add_column("Failure Rate", style="red")

                    for test in result.top_failures[:10]:  # Limit to 10 for readability
                        if hasattr(test, "failure_rate") and hasattr(test, "nodeid"):
                            failure_table.add_row(test.nodeid, f"{test.failure_rate:.1%}")

                    console.print(failure_table)

                if (
                    "top_unreliable" in sections_to_include
                    and hasattr(result, "unreliable_tests")
                    and result.unreliable_tests
                ):
                    console.print("\n[bold yellow]Top Unreliable Tests:[/bold yellow]")
                    unreliable_table = Table(show_header=True, header_style="bold yellow")
                    unreliable_table.add_column("Test", style="cyan")
                    unreliable_table.add_column("Unreliable Rate", style="yellow")

                    for test in result.unreliable_tests[:10]:  # Limit to 10 for readability
                        if hasattr(test, "nonreliability_rate") and hasattr(test, "nodeid"):
                            unreliable_table.add_row(test.nodeid, f"{test.nonreliability_rate:.1%}")

                    console.print(unreliable_table)

                if "performance_issues" in sections_to_include and hasattr(result, "slow_tests") and result.slow_tests:
                    console.print("\n[bold cyan]Performance Issues:[/bold cyan]")
                    perf_table = Table(show_header=True, header_style="bold magenta")
                    perf_table.add_column("Test", style="cyan")
                    perf_table.add_column("Duration (s)", style="magenta")

                    for test in result.slow_tests[:10]:  # Limit to 10 for readability
                        if hasattr(test, "duration") and hasattr(test, "nodeid"):
                            perf_table.add_row(test.nodeid, f"{test.duration:.2f}")

                    console.print(perf_table)

                # Recommendations
                console.print("\nRecommendations:", style="bold")

                # Get metrics from the result dictionary
                pass_rate = result["session_metrics"].get("pass_rate", 0)
                reliability_index = (
                    result["reliability_metrics"].get("reliability_index", 100)
                    if "reliability_metrics" in result
                    else 100
                )
                rerun_recovery_rate = (
                    result["reliability_metrics"].get("rerun_recovery_rate", 100)
                    if "reliability_metrics" in result
                    else 100
                )

                recommendations = []

                # Test stability recommendations
                if "reliability_metrics" in result and reliability_index < 95:
                    recommendations.append(
                        "- Low reliability index detected. Consider investigating test stability issues."
                    )
                    if "reliability_metrics" in result and rerun_recovery_rate > 70:
                        recommendations.append("  ✓ Good rerun recovery rate. Focus on tests that fail consistently.")
                    else:
                        recommendations.append("  ✗ Low rerun recovery rate. Tests may have genuine failures.")

                # Pass rate recommendations
                if pass_rate < 0.9:
                    recommendations.append("- Low pass rate detected. Consider investigating test failures.")

                if not recommendations:
                    console.print("- No issues detected. Test suite is healthy!", style="green")
                else:
                    for rec in recommendations:
                        if rec.startswith("  ✓"):
                            console.print(rec, style="green")
                        elif rec.startswith("  ✗"):
                            console.print(rec, style="red")
                        else:
                            console.print(rec)

                # Predictive analytics
                console.print("\n[bold]Predictive Analytics:[/bold]")
                console.print("  - Run 'insight predict' to generate predictive analytics for this SUT.")

        elif report_type == "stability":
            # Get consistently failing and unreliable tests
            failing_tests = analyzer.identify_consistently_failing_tests()
            unreliable_tests = analyzer.identify_unreliable_tests()

            if format == OutputFormat.JSON:
                import json

                result_dict = {
                    "consistently_failing_tests": failing_tests,
                    "unreliable_tests": unreliable_tests,
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

                if unreliable_tests:
                    table = Table(
                        title="Unreliable Tests",
                        show_header=True,
                        header_style="bold yellow",
                    )
                    table.add_column("Test", style="cyan")

                    for test in unreliable_tests[:20]:  # Limit to 20 tests for readability
                        table.add_row(test)

                    if len(unreliable_tests) > 20:
                        table.add_row(f"... and {len(unreliable_tests) - 20} more")

                    console.print(table)
                else:
                    console.print("[green]No unreliable tests found.[/green]")

        elif report_type == "performance":
            # Get slowest tests
            slowest_tests = analyzer.get_slowest_tests(limit=20)

            if format == OutputFormat.JSON:
                import json

                result_dict = {
                    "slowest_tests": [{"nodeid": test.nodeid, "duration": test.duration} for test in slowest_tests],
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
                    console.print("  - Consider optimizing tests that take longer than 1 second")
                    console.print("  - Look for common patterns in slow tests (e.g., database access, file I/O)")
                else:
                    console.print("[yellow]No test duration data available.[/yellow]")

        elif report_type == "unreliable":
            # Focus specifically on unreliable tests
            unreliable_tests = analyzer.identify_unreliable_tests()

            if format == OutputFormat.JSON:
                import json

                result_dict = {
                    "unreliable_tests": unreliable_tests,
                    "count": len(unreliable_tests),
                    "days_analyzed": days,
                }

                print(json.dumps(result_dict, indent=2))
            else:
                # Rich text output for unreliable tests report
                title_parts = ["\n[bold blue]Unreliable Tests Report"]
                if sut:
                    title_parts.append(f" for [yellow]{sut}[/yellow]")
                title_parts.append(f" (Last {days} days)\n")
                console.print("".join(title_parts))

                if unreliable_tests:
                    table = Table(
                        title=f"Unreliable Tests ({len(unreliable_tests)} found)",
                        show_header=True,
                        header_style="bold yellow",
                    )
                    table.add_column("Test", style="cyan")

                    for test in unreliable_tests[:30]:  # Limit to 30 tests for readability
                        table.add_row(test)

                    if len(unreliable_tests) > 30:
                        table.add_row(f"... and {len(unreliable_tests) - 30} more")

                    console.print(table)

                    # Recommendations for unreliable tests
                    console.print("\n[bold]Recommendations for Addressing Unreliable Tests:[/bold]")
                    console.print(
                        "  1. [yellow]Identify patterns[/yellow] - Look for common factors (async, timing, resources)"
                    )
                    console.print(
                        "  2. [yellow]Isolate and reproduce[/yellow] - Try to reproduce the reliability-repeatability locally"
                    )
                    console.print(
                        "  3. [yellow]Add logging[/yellow] - Enhance logging to capture more context when tests fail"
                    )
                    console.print(
                        "  4. [yellow]Consider quarantine[/yellow] - Move highly unreliable tests to a separate suite"
                    )
                else:
                    console.print("[green]No unreliable tests found in the analyzed period.[/green]")

        else:
            console.print(f"[bold red]Error:[/bold red] Unknown report type: {report_type}")
            console.print("Available report types: health, stability, performance, unreliable")

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
    test_pattern: Optional[str] = typer.Option(None, help="Test pattern (supports wildcards)"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
    insight_type: str = typer.Option("summary", help="Type of insights (summary, patterns, trends, dependencies)"),
    format: OutputFormat = typer.Option(OutputFormat.TEXT, help="Output format (text or json)"),
    config_file: Optional[str] = typer.Option(None, help="Path to configuration file"),
    include_metrics: Optional[str] = typer.Option(
        None,
        help="Comma-separated list of metrics to include (e.g., 'pass_rate,reliability_rate')",
    ),
    include_sections: Optional[str] = typer.Option(
        None,
        help="Comma-separated list of sections to include (e.g., 'top_failures,top_unreliable')",
    ),
    exclude_metrics: Optional[str] = typer.Option(None, help="Comma-separated list of metrics to exclude"),
    exclude_sections: Optional[str] = typer.Option(None, help="Comma-separated list of sections to exclude"),
):
    """Generate insights from test data.

    This command generates various types of insights from test data, including summary reports, error patterns, stability trends, and test dependencies.

    The insights can be configured using a configuration file or command-line options to specify which metrics and sections to include or exclude.
    """
    console = Console()

    try:
        # Load configuration
        from pytest_insight.core.config import load_config

        # Fix the config_file parameter to handle typer.Option objects
        if isinstance(config_file, typer.models.OptionInfo):
            config_file = None

        config = load_config(config_file)

        # Create API instance
        api = InsightAPI()
        if profile:
            api = api.with_profile(profile)

        # Build query
        query = api.query()
        if sut:
            query = query.with_sut(sut)
        query = query.in_last_days(days)

        # Execute the query to get filtered sessions
        result = query.execute()

        # Create insights instance with the query
        insight_api = api.insights().with_query(result)

        # Apply command-line overrides for metrics and sections
        if include_metrics or exclude_metrics or include_sections or exclude_sections:
            if "reports" not in config:
                config["reports"] = {}
            if insight_type not in config["reports"]:
                config["reports"][insight_type] = {}

            # Handle metrics
            if include_metrics:
                config["reports"][insight_type]["metrics"] = [m.strip() for m in include_metrics.split(",")]
            elif exclude_metrics and "metrics" in config["reports"][insight_type]:
                exclude_list = [m.strip() for m in exclude_metrics.split(",")]
                config["reports"][insight_type]["metrics"] = [
                    m for m in config["reports"][insight_type]["metrics"] if m not in exclude_list
                ]

            # Handle sections
            if include_sections:
                config["reports"][insight_type]["sections"] = [s.strip() for s in include_sections.split(",")]
            elif exclude_sections and "sections" in config["reports"][insight_type]:
                exclude_list = [s.strip() for s in exclude_sections.split(",")]
                config["reports"][insight_type]["sections"] = [
                    s for s in config["reports"][insight_type]["sections"] if s not in exclude_list
                ]

        # Apply configuration if we have any overrides
        if config:
            insight_api = insight_api.with_config(config)

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
                    "reliability_index": (result.reliability_index if hasattr(result, "reliability_index") else 0),
                    "rerun_recovery_rate": (
                        result.rerun_recovery_rate if hasattr(result, "rerun_recovery_rate") else 0
                    ),
                    "top_failures": result.top_failures,
                    "top_unreliable": result.top_unreliable,
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
                table.add_row(
                    "Reliability Index",
                    (f"{result.reliability_index:.2f}" if hasattr(result, "reliability_index") else "N/A"),
                )
                table.add_row(
                    "Rerun Recovery Rate",
                    (f"{result.rerun_recovery_rate:.1%}" if hasattr(result, "rerun_recovery_rate") else "N/A"),
                )

                console.print(table)

                # Top failures
                if result.top_failures:
                    console.print("\n[bold red]Top Failing Tests:[/bold red]")
                    for i, test in enumerate(result.top_failures[:5], 1):
                        console.print(f"  {i}. {test}")

                # Top unreliable tests
                if result.top_unreliable:
                    console.print("\n[bold yellow]Top Unreliable Tests:[/bold yellow]")
                    for i, test in enumerate(result.top_unreliable[:5], 1):
                        console.print(f"  {i}. {test}")

                # Performance issues
                if result.performance_issues:
                    console.print("\n[bold cyan]Performance Issues:[/bold cyan]")
                    for i, issue in enumerate(result.performance_issues[:5], 1):
                        console.print(f"  {i}. {issue}")

                # Overall assessment
                console.print("\n[bold]Overall Assessment:[/bold]")
                if result.pass_rate >= 0.95 and result.reliability_index >= 95:
                    console.print("[bold green]Excellent[/bold green] - Test suite is healthy and stable.")
                elif result.pass_rate >= 0.85 and result.reliability_index >= 85:
                    console.print(
                        "[bold yellow]Good[/bold yellow] - Test suite is generally healthy with minor issues."
                    )
                else:
                    console.print(
                        "[bold red]Needs Attention[/bold red] - Test suite has significant issues to address."
                    )

                # Recommendations
                console.print("\nRecommendations:", style="bold")

                # Get metrics from the result dictionary
                pass_rate = result["session_metrics"].get("pass_rate", 0)
                reliability_index = (
                    result["reliability_metrics"].get("reliability_index", 100)
                    if "reliability_metrics" in result
                    else 100
                )
                rerun_recovery_rate = (
                    result["reliability_metrics"].get("rerun_recovery_rate", 100)
                    if "reliability_metrics" in result
                    else 100
                )

                recommendations = []

                # Test stability recommendations
                if "reliability_metrics" in result and reliability_index < 95:
                    recommendations.append(
                        "- Low reliability index detected. Consider investigating test stability issues."
                    )
                    if "reliability_metrics" in result and rerun_recovery_rate > 70:
                        recommendations.append("  ✓ Good rerun recovery rate. Focus on tests that fail consistently.")
                    else:
                        recommendations.append("  ✗ Low rerun recovery rate. Tests may have genuine failures.")

                # Pass rate recommendations
                if pass_rate < 0.9:
                    recommendations.append("- Low pass rate detected. Consider investigating test failures.")

                if not recommendations:
                    console.print("- No issues detected. Test suite is healthy!", style="green")
                else:
                    for rec in recommendations:
                        if rec.startswith("  ✓"):
                            console.print(rec, style="green")
                        elif rec.startswith("  ✗"):
                            console.print(rec, style="red")
                        else:
                            console.print(rec)

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

                    for pattern in result.patterns[:10]:  # Limit to 10 patterns for readability
                        example_tests = ", ".join(pattern.example_tests[:2])
                        if len(pattern.example_tests) > 2:
                            example_tests += "..."
                        table.add_row(pattern.pattern, str(pattern.frequency), example_tests)

                    console.print(table)

                    # Recommendations
                    console.print("\n[bold]Pattern Analysis Recommendations:[/bold]")
                    console.print("  - Look for common root causes in tests with similar error patterns")
                    console.print("  - Consider refactoring test fixtures or setup code for recurring patterns")
                else:
                    console.print("[green]No significant error patterns found in the analyzed period.[/green]")

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
                            "reliability_index": point.reliability_index,
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
                    table.add_column("Reliability Index", style="yellow")

                    for point in result.timeline:
                        table.add_row(
                            str(point.date),
                            f"{point.pass_rate:.1%}",
                            f"{point.reliability_index:.2f}",
                        )

                    console.print(table)

                    # Trend assessment
                    console.print("\n[bold]Trend Assessment:[/bold]")
                    if result.trend == "improving":
                        console.print("[bold green]Improving[/bold green] - Test stability is trending upward.")
                    elif result.trend == "stable":
                        console.print("[bold blue]Stable[/bold blue] - Test stability is consistent.")
                    elif result.trend == "declining":
                        console.print("[bold red]Declining[/bold red] - Test stability is trending downward.")
                    else:
                        console.print("[bold yellow]Inconclusive[/bold yellow] - Not enough data to determine trend.")
                else:
                    console.print("[yellow]Insufficient data for trend analysis.[/yellow]")

        elif insight_type == "dependencies":
            result = insight_api.test_insights().dependency_graph()

            if format == OutputFormat.JSON:
                import json

                # Convert result to JSON-serializable dict
                result_dict = {
                    "nodes": [{"id": node.id, "type": node.type} for node in result.nodes],
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
                        console.print(f"  ... and {len(result.clusters) - 5} more clusters")

                    # Show high-impact nodes
                    console.print("\n[bold]High-Impact Components:[/bold]")
                    high_impact = sorted(
                        result.nodes,
                        key=lambda n: sum(e.weight for e in result.edges if e.source == n.id or e.target == n.id),
                        reverse=True,
                    )
                    for node in high_impact[:5]:
                        console.print(f"  - {node.id} ({node.type})")

                    # Show contributing factors
                    if result.contributing_factors:
                        console.print("\n[bold]Contributing Factors:[/bold]")
                        for factor in result.contributing_factors:
                            console.print(f"  • {factor}")

                    # Add recommendations based on trend
                    console.print("\n[bold]Recommendations:[/bold]")
                    console.print("  - Consider refactoring highly connected components to reduce coupling")
                    console.print("  - Look for opportunities to parallelize isolated test clusters")
                else:
                    console.print("[yellow]Insufficient data for dependency analysis.[/yellow]")

        else:
            console.print(f"[bold red]Error:[/bold red] Unknown insight type: {insight_type}")
            console.print("Available insight types: summary, patterns, trends, dependencies")

    except Exception as e:
        if format == OutputFormat.JSON:
            import json

            print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")
            console.print(traceback.format_exc(), style="red")


@app.command("predict")
def cli_predict(
    prediction_type: str = typer.Argument(
        "failures",
        help="Type of prediction to generate (failures, anomalies, stability)",
    ),
    sut: Optional[str] = typer.Option(None, help="System Under Test (SUT) to analyze"),
    days: int = typer.Option(30, help="Number of days to include in analysis"),
    days_ahead: int = typer.Option(7, help="Number of days to predict ahead"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
    format: OutputFormat = typer.Option(OutputFormat.TEXT, help="Output format (text or json)"),
    config_file: Optional[str] = typer.Option(None, help="Path to configuration file"),
):
    """Generate predictive analytics from test data.

    This command uses machine learning and statistical analysis to predict future test behavior,
    detect anomalies, and forecast stability trends.

    Examples:
        insight predict failures --sut my-service
        insight predict anomalies --days 60
        insight predict stability --profile production
    """
    console = Console()

    try:
        # Load configuration if provided
        if config_file:
            load_config(config_file)

        # Create API instance
        predictive_api = core_get_predictive(core_analyze(profile_name=profile))

        # Apply SUT filter if specified
        if sut and hasattr(predictive_api.analysis, "_sessions"):
            filtered_sessions = []
            for session in predictive_api.analysis._sessions:
                if hasattr(session, "sut") and session.sut == sut:
                    filtered_sessions.append(session)
            predictive_api.analysis._sessions = filtered_sessions

        # Generate the requested prediction
        if prediction_type == "failures":
            result = predictive_api.failure_prediction(days_ahead=days_ahead)

            if format == OutputFormat.JSON:
                import json

                print(json.dumps(result, indent=2))
            else:
                # Rich text output for failure prediction
                title_parts = ["\n[bold blue]Test Failure Predictions"]
                if sut:
                    title_parts.append(f" for [yellow]{sut}[/yellow]")
                title_parts.append(f" (Next {days_ahead} days)\n")
                console.print("".join(title_parts))

                if "error" in result:
                    console.print(f"[bold red]Error:[/bold red] {result['error']}")
                    return

                # Display high risk tests
                if result["high_risk_tests"]:
                    console.print("[bold]High Risk Tests:[/bold] (Failure Probability > 70%)")
                    table = Table(show_header=True, header_style="bold magenta")
                    table.add_column("Test", style="cyan")
                    table.add_column("Failure Probability", style="red")
                    table.add_column("Recent Failures", style="yellow")

                    for test in result["high_risk_tests"][:10]:  # Show top 10
                        table.add_row(
                            test["nodeid"],
                            f"{test['probability'] * 100:.1f}%",
                            str(test["recent_failures"]),
                        )

                    console.print(table)

                    # Show prediction confidence
                    confidence = result["confidence"] * 100
                    confidence_color = "green" if confidence > 70 else "yellow" if confidence > 40 else "red"
                    console.print(
                        f"\nPrediction Confidence: [bold {confidence_color}]{confidence:.1f}%[/bold {confidence_color}]"
                    )

                    # Add recommendations
                    console.print("\n[bold]Recommendations:[/bold]")
                    console.print("  • Prioritize fixing high-risk tests to prevent future failures")
                    console.print("  • Consider adding more test coverage for unstable components")
                    if confidence < 70:
                        console.print("  • Collect more test data to improve prediction accuracy")
                else:
                    console.print("[green]No high-risk tests identified for the upcoming period.[/green]")
                    console.print("\nAll tests are predicted to be stable.")

        elif prediction_type == "anomalies":
            result = predictive_api.anomaly_detection()

            if format == OutputFormat.JSON:
                import json

                print(json.dumps(result, indent=2))
            else:
                # Rich text output for anomaly detection
                title_parts = ["\n[bold blue]Test Anomaly Detection"]
                if sut:
                    title_parts.append(f" for [yellow]{sut}[/yellow]")
                title_parts.append("\n")
                console.print("".join(title_parts))

                if "error" in result:
                    console.print(f"[bold red]Error:[/bold red] {result['error']}")
                    return

                # Display anomalous tests
                if result["anomalies"]:
                    console.print("[bold]Anomalous Tests:[/bold] (Anomaly Score > 70%)")
                    table = Table(show_header=True, header_style="bold magenta")
                    table.add_column("Test", style="cyan")
                    table.add_column("Anomaly Score", style="red")
                    table.add_column("Mean Duration", style="yellow")
                    table.add_column("Failure Rate", style="yellow")

                    for test in result["anomalies"][:10]:  # Show top 10
                        table.add_row(
                            test["nodeid"],
                            f"{test['score'] * 100:.1f}%",
                            f"{test['features']['mean_duration']:.3f}s",
                            f"{test['features']['failure_rate'] * 100:.1f}%",
                        )

                    console.print(table)

                    # Show detection confidence
                    confidence = result["detection_confidence"] * 100
                    confidence_color = "green" if confidence > 70 else "yellow" if confidence > 40 else "red"
                    console.print(
                        f"\nDetection Confidence: [bold {confidence_color}]{confidence:.1f}%[/bold {confidence_color}]"
                    )

                    # Add recommendations
                    console.print("\n[bold]Recommendations:[/bold]")
                    console.print("  • Investigate anomalous tests for potential issues")
                    console.print("  • Check for environmental factors affecting these tests")
                    console.print("  • Consider refactoring tests with unusual behavior patterns")
                else:
                    console.print("[green]No anomalous tests detected in the current dataset.[/green]")

        elif prediction_type == "stability":
            result = predictive_api.stability_forecast()

            if format == OutputFormat.JSON:
                import json

                print(json.dumps(result, indent=2))
            else:
                # Rich text output for stability forecast
                title_parts = ["\n[bold blue]Test Stability Forecast"]
                if sut:
                    title_parts.append(f" for [yellow]{sut}[/yellow]")
                title_parts.append("\n")
                console.print("".join(title_parts))

                if "error" in result:
                    console.print(f"[bold red]Error:[/bold red] {result['error']}")
                    return

                # Display stability forecast
                current = result.get("current_stability")
                forecast = result.get("forecasted_stability")

                if current is not None and forecast is not None:
                    # Create a table for stability scores
                    table = Table(show_header=True, header_style="bold magenta")
                    table.add_column("Metric", style="cyan")
                    table.add_column("Score", style="green")

                    # Determine color for current stability
                    current_color = "green" if current > 80 else "yellow" if current > 60 else "red"
                    table.add_row(
                        "Current Stability",
                        f"[bold {current_color}]{current:.1f}%[/bold {current_color}]",
                    )

                    # Determine color for forecasted stability
                    forecast_color = "green" if forecast > 80 else "yellow" if forecast > 60 else "red"
                    table.add_row(
                        "Forecasted Stability",
                        f"[bold {forecast_color}]{forecast:.1f}%[/bold {forecast_color}]",
                    )

                    # Calculate change
                    change = forecast - current
                    change_sign = "+" if change > 0 else ""
                    change_color = "green" if change > 0 else "red" if change < 0 else "blue"
                    table.add_row(
                        "Projected Change",
                        f"[bold {change_color}]{change_sign}{change:.1f}%[/bold {change_color}]",
                    )

                    console.print(table)

                    # Show trend direction
                    trend = result["trend_direction"]
                    trend_color = "green" if trend == "improving" else "red" if trend == "declining" else "blue"
                    console.print(f"\nTrend Direction: [bold {trend_color}]{trend.capitalize()}[/bold {trend_color}]")

                    # Show contributing factors
                    if result["contributing_factors"]:
                        console.print("\n[bold]Contributing Factors:[/bold]")
                        for factor in result["contributing_factors"]:
                            console.print(f"  • {factor}")

                    # Add recommendations based on trend
                    console.print("\n[bold]Recommendations:[/bold]")
                    if trend == "declining":
                        console.print("  - Investigate factors causing stability decline")
                        console.print("  - Focus on improving test reliability and reducing reliability-repeatability")
                        console.print("  - Consider implementing more robust test infrastructure")
                    elif trend == "improving":
                        console.print("  - Continue current testing practices that are improving stability")
                        console.print("  - Document successful strategies for future reference")
                        console.print("  - Consider applying similar approaches to other test suites")
                    else:
                        console.print("  - Monitor stability metrics to detect any future changes")
                        console.print("  - Implement proactive measures to improve test reliability")
                else:
                    console.print("[yellow]Insufficient data for stability forecast.[/yellow]")

        else:
            console.print(f"[bold red]Error:[/bold red] Unknown prediction type: {prediction_type}")
            console.print("Available prediction types: failures, anomalies, stability")

    except Exception as e:
        if format == OutputFormat.JSON:
            import json

            print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")
            console.print(traceback.format_exc(), style="red")


@app.command("analyze_patterns")
def cli_analyze_patterns(
    sut: Optional[str] = typer.Option(None, help="System Under Test to analyze"),
    days: int = typer.Option(10, help="Number of days to include in analysis"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
):
    """Analyze test patterns such as emerging failures, slowdowns, or correlated issues.

    Args:
        sut (str, optional): System Under Test to analyze. Defaults to None (all SUTs).
        days (int, optional): Number of days to include in analysis. Defaults to 10.
        profile (str, optional): Storage profile to use. Defaults to None (active profile).

    Returns:
        None. Prints results to the console.
    """
    from rich.console import Console
    from rich.table import Table
    from pytest_insight.core.core_api import InsightAPI
    from pytest_insight.facets.trend import TrendInsight

    console = Console()
    api = InsightAPI(profile_name=profile)
    analysis = api.analyze()
    if sut:
        analysis = analysis.for_sut(sut)
    sessions = analysis.sessions.last_n_days(days=days)
    if not sessions:
        console.print(f"[yellow]No sessions found in the last {days} days.[/yellow]")
        return
    trend = TrendInsight(sessions)
    patterns = trend.emerging_patterns()
    if not patterns:
        console.print(f"[green]No emerging patterns detected in the last {days} days.[/green]")
        return
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Test NodeID", style="cyan")
    table.add_column("Issue", style="red")
    table.add_column("Details", style="green")
    for p in patterns:
        details = []
        if "recent_failure_time" in p:
            details.append(f"Last fail: {p['recent_failure_time']}")
        if "max_duration" in p:
            details.append(f"Max duration: {p['max_duration']:.2f}s")
        table.add_row(p["nodeid"], p["issue"], ", ".join(details))
    console.print(table)


if __name__ == "__main__":
    app()
