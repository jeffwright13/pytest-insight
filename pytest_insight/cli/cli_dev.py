"""Developer CLI functionality for pytest-insight."""

import inspect
import traceback
from enum import Enum
from typing import Any, Callable, Dict, List

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
from pytest_insight.core.insights import Insights
from pytest_insight.core.query import Query

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

    # Initialize context
    context = {
        "active_profile": "default",
        "queries": {},  # Store queries by name
        "results": {},  # Store results by name
        "current_query": None,
        "current_result": None,
        "in_test_filter": False,  # Flag to track if we're in a test filter context
        "test_filter_builder": None,  # Store the TestFilterBuilder
        "history": [],  # Store command history with results
    }

    # Define available commands and completions
    commands = [
        "help",
        "exit",
        "quit",
        "history",
        "clear",
        "profile list",
        "profile create",
        "profile switch",
        "profile active",
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
        "query chain",  # Added query chain command
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

    session = PromptSession(history=history, completer=completer, style=style)

    # Main loop
    while True:
        try:
            # Get user input with current profile in prompt
            user_input = session.prompt(f"\n[pytest-insight:{context['active_profile']}] > ")

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
                console.print("\033c", end="")
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
                    profiles = ["default"]
                    active_profile = context["active_profile"]

                    table = Table(title="Storage Profiles")
                    table.add_column("Profile Name")
                    table.add_column("Path")
                    table.add_column("Active")

                    for profile in profiles:
                        is_active = "✓" if profile == active_profile else ""
                        table.add_row(profile, "", is_active)

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
                    from pytest_insight.core.query import Query

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
                            table.add_column("Test Run ID")
                            table.add_column("SUT")
                            table.add_column("Timestamp")
                            table.add_column("Tests")

                            for session in result.sessions[:10]:  # Limit to 10 sessions for display
                                table.add_row(
                                    session.id,
                                    session.test_run_id,
                                    session.sut or "N/A",
                                    str(session.timestamp),
                                    str(len(session.tests)),
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
                        # Create a test filter builder if not already in test filter mode
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
                    from pytest_insight.core.query import Query

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
                        table.add_column("Test Run ID")
                        table.add_column("SUT")
                        table.add_column("Timestamp")
                        table.add_column("Tests")

                        for session in result.sessions[:10]:  # Limit to 10 sessions for display
                            table.add_row(
                                session.id,
                                session.test_run_id,
                                session.sut or "N/A",
                                str(session.timestamp),
                                str(len(session.tests)),
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

                    test_count1 = sum(len(s.tests) for s in result1.sessions)
                    test_count2 = sum(len(s.tests) for s in result2.sessions)
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
            elif command == "session":
                if len(parts) < 2:
                    console.print("[bold red]Error:[/bold red] Missing session subcommand")
                    context["history"][history_index]["result"] = {"error": "Missing session subcommand"}
                    continue

                subcommand = parts[1].lower()

                if subcommand == "list":
                    if not context["current_result"] or not context["current_result"].sessions:
                        console.print("[bold red]Error:[/bold red] No active result with sessions")
                        context["history"][history_index]["result"] = {"error": "No active result with sessions"}
                        continue

                    table = Table(title="Sessions")
                    table.add_column("Session ID")
                    table.add_column("Test Run ID")
                    table.add_column("SUT")
                    table.add_column("Timestamp")
                    table.add_column("Tests")

                    for session in context["current_result"].sessions:
                        table.add_row(
                            session.id,
                            session.test_run_id,
                            session.sut or "N/A",
                            str(session.timestamp),
                            str(len(session.tests)),
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

                    console.print(f"Session: [bold]{session.id}[/bold]")
                    console.print(f"Test Run ID: {session.test_run_id}")
                    console.print(f"SUT: {session.sut or 'N/A'}")
                    console.print(f"Timestamp: {session.timestamp}")
                    console.print(f"Tests: {len(session.tests)}")

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

                    table = Table(title=f"Tests in Session {session.id}")
                    table.add_column("Test ID")
                    table.add_column("Nodeid")
                    table.add_column("Outcome")
                    table.add_column("Duration (s)")

                    for test in session.tests:
                        table.add_row(
                            test.id,
                            test.nodeid,
                            test.outcome,
                            (str(round(test.duration, 3)) if test.duration is not None else "N/A"),
                        )

                    console.print(table)
                    context["history"][history_index]["result"] = {
                        "summary": f"Listed {len(session.tests)} tests in session {session_id}"
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

                    failures = [t for t in session.tests if t.outcome == "failed"]

                    if not failures:
                        console.print(f"No failures in session {session.id}")
                        context["history"][history_index]["result"] = {
                            "summary": f"No failures in session {session_id}"
                        }
                        continue

                    table = Table(title=f"Failures in Session {session.id}")
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


if __name__ == "__main__":
    app()
