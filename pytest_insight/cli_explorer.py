"""
pytest-insight Fluent CLI Explorer

A Pythonic, chainable, immediate-feedback CLI for exploring test session data and insights.

Usage:
    $ python -m pytest_insight.cli_explorer
    > query.for_sut("foo").in_last_days(7).filter_by_test().with_outcome("fail").apply().execute()
    Sessions: 4 | SUT: foo | Time: last 7d | Filters: failures
    > analyze.flakiness()
    ...

Type 'help' for available commands/facets/insights.
Type 'show_query' to export the current query as Python code.
Type 'exit' or 'quit' to leave.
"""
import sys
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import importlib.util
import os

# Import the core API (do NOT touch v1 folders)
from pytest_insight.core.query import SessionQuery
# from pytest_insight.core.insights import TestInsights
from pytest_insight.utils.test_data import random_test_sessions

# Dynamically import Analysis from v1 core/analysis.py to avoid __init__.py import loop
v1_analysis_path = os.path.join(os.path.dirname(__file__), '../pytest_insight_v1/core/analysis.py')
spec = importlib.util.spec_from_file_location("v1_analysis", os.path.abspath(v1_analysis_path))
v1_analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v1_analysis)
V1Analysis = v1_analysis.Analysis

console = Console()

# --- Helper functions ---
def format_status(context):
    """Return a status line summarizing the current query context."""
    if not context.get('last_result'):
        return "No results yet."
    sessions = context['last_result']
    sut = context.get('sut', 'all')
    time = context.get('time', 'all')
    filters = ', '.join(context.get('filters', [])) or 'none'
    return f"Sessions: {len(sessions)} | SUT: {sut} | Time: {time} | Filters: {filters}"

def print_sessions(sessions):
    """Pretty-print a summary table of sessions."""
    table = Table(title="Test Sessions", show_lines=True)
    table.add_column("Session ID")
    table.add_column("SUT")
    table.add_column("Start Time")
    table.add_column("# Tests")
    for s in sessions:
        table.add_row(str(getattr(s, 'session_id', '?')), str(getattr(s, 'sut', '?')), str(getattr(s, 'session_start_time', '?')), str(len(getattr(s, 'test_results', []))))
    console.print(table)

def print_flakiness(flakiness):
    table = Table(title="Flakiness Analysis", show_lines=True)
    table.add_column("Test Name")
    table.add_column("Flaky?")
    table.add_column("Pass Count")
    table.add_column("Fail Count")
    for test_name, result in flakiness.items():
        table.add_row(test_name, str(result['flaky']), str(result['passes']), str(result['fails']))
    console.print(table)

def print_error_patterns(patterns):
    table = Table(title="Error Patterns", show_lines=True)
    table.add_column("Pattern")
    table.add_column("Test Count")
    for pattern, tests in patterns.items():
        table.add_row(pattern, str(len(tests)))
    console.print(table)

# --- Main CLI Loop ---
def main():
    session = PromptSession()
    # Generate demo sessions
    demo_sessions = random_test_sessions(25)
    context = {
        'query': SessionQuery(demo_sessions),
        'last_result': demo_sessions,
        'sut': 'all',
        'time': 'all',
        'filters': [],
    }
    completer = WordCompleter([
        'query.for_sut(', 'in_last_days(', 'filter_by_test()', 'with_outcome(', 'apply()', 'execute()',
        'analyze.flakiness()', 'insights.error_patterns()', 'show_query', 'help', 'exit', 'quit', 'list_suts'
    ], ignore_case=True)
    console.print(Panel("[bold cyan]pytest-insight Fluent CLI Explorer[/bold cyan]\nType 'help' for commands. Type 'exit' to quit.", expand=False))
    while True:
        try:
            status = format_status(context)
            user_input = session.prompt(f"[{status}]\n> ", completer=completer)
            cmd = user_input.strip()
            if cmd in ('exit', 'quit'):
                break
            elif cmd == 'help':
                console.print("""
[bold]Available commands:[/bold]
- query.for_sut("foo")
- in_last_days(N)
- filter_by_test()
- with_outcome("fail")
- apply()
- execute()
- analyze.flakiness()
- insights.error_patterns()
- show_query
- list_suts
- help
- exit/quit
[italic]Chain commands as in Python. E.g. query.for_sut("foo").in_last_days(7).filter_by_test().with_outcome("fail").apply().execute()[/italic]
""")
            elif cmd == 'show_query':
                console.print(f"Current query: [green]{context.get('query_str','(none)')}[/green]")
            elif cmd == 'list_suts':
                # List all unique SUT names from the current result set
                sessions = context.get('last_result')
                if not sessions:
                    console.print("[yellow]No sessions loaded. Run a query first.[/yellow]")
                else:
                    suts = sorted(set(getattr(s, 'sut_name', None) for s in sessions if hasattr(s, 'sut_name')))
                    console.print(f"[bold cyan]Available SUTs:[/bold cyan] {', '.join(suts) if suts else '[none]'}")
            elif cmd.startswith('query.') or cmd.startswith('in_last_days(') or cmd.startswith('filter_by_test()') or cmd.startswith('with_outcome(') or cmd.startswith('apply()') or cmd.startswith('execute()'):
                # Evaluate the chainable query
                try:
                    # Build up the query string
                    if cmd.startswith('query.'):
                        context['query_str'] = cmd
                        q = eval(cmd, {'query': SessionQuery(demo_sessions)})
                    else:
                        # Chain onto previous query
                        prev = context.get('query')
                        q = eval(f'prev.{cmd}', {'prev': prev})
                        context['query_str'] = (context.get('query_str','query') + '.' + cmd)
                    # If .execute() is called, update last_result
                    if '.execute()' in cmd:
                        sessions = q.execute() if hasattr(q, 'execute') else q
                        context['last_result'] = sessions
                        print_sessions(sessions)
                    else:
                        context['query'] = q
                except Exception as e:
                    console.print(f"[red]Error evaluating query:[/red] {e}")
            elif cmd.startswith('analyze.flakiness()'):
                try:
                    sessions = context.get('last_result')
                    if not sessions:
                        console.print("[yellow]No sessions to analyze. Run a query first.[/yellow]")
                        continue
                    analysis = V1Analysis(sessions)
                    flakiness = analysis.identify_flaky_tests()
                    print_flakiness(flakiness)
                except Exception as e:
                    console.print(f"[red]Error running flakiness analysis:[/red] {e}")
            elif cmd.startswith('insights.error_patterns()'):
                try:
                    sessions = context.get('last_result')
                    if not sessions:
                        console.print("[yellow]No sessions to analyze. Run a query first.[/yellow]")
                        continue
                    # insights = TestInsights(sessions)
                    # patterns = insights.error_patterns()
                    console.print("[yellow]Error patterns insights are not available in this version.[/yellow]")
                except Exception as e:
                    console.print(f"[red]Error running error pattern insights:[/red] {e}")
            else:
                console.print(f"[yellow]Unknown command:[/yellow] {cmd}")
        except (KeyboardInterrupt, EOFError):
            break
    console.print("[bold green]Goodbye![/bold green]")

if __name__ == "__main__":
    main()
