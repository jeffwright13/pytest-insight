"""
Dashboard formatter for pytest-insight terminal output.
Formats summary tables, test insights, and sparklines for trends.
"""

import io
import re
import shutil
from typing import Any

from sparklines import sparklines
from tabulate import tabulate

try:
    from rich import box
    from rich.columns import Columns
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def strip_ansi_codes(val):
    # Remove ANSI escape sequences (use the same regex as the test's strip_ansi)
    ansi_escape = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
    return ansi_escape.sub("", val)


def sparkline(data: Any) -> str:
    return "".join(sparklines(data)) if data else ""


def render_summary(api, section_cfg, terminal_config, return_panel=False):
    summary = api.session_dict()
    # Fallback for DummyAPI in tests
    if not summary or not isinstance(summary, dict) or not getattr(summary, "keys", lambda: [])():
        if hasattr(api, "_summary"):
            summary = getattr(api, "_summary", {})
    if isinstance(summary, dict):
        # Attempt to extract SUT and system name for panel title
        sut_name = None
        system_name = None
        if hasattr(api, "session"):
            session_obj = api.session()
            if hasattr(session_obj, "sessions") and session_obj.sessions:
                first_sess = session_obj.sessions[0]
                sut_name = getattr(first_sess, "sut_name", None)
                system_name = getattr(first_sess, "testing_system", None)
                if isinstance(system_name, dict):
                    system_name = system_name.get("name") or next(iter(system_name.values()), None)
        panel_title = "[green]Summary"
        if sut_name or system_name:
            panel_title += " ("
            if sut_name:
                panel_title += f"SUT={sut_name}"
            if system_name:
                if sut_name:
                    panel_title += " "
                panel_title += f"System={system_name}"
            panel_title += ")"
        display_keys = section_cfg.get("fields")
        if not display_keys:
            display_keys = [
                k
                for k in [
                    "total_sessions",
                    "total_tests",
                    "pass_rate",
                    "fail_rate",
                    "avg_duration",
                    "median_duration",
                    "min_duration",
                    "max_duration",
                ]
                if k in summary
            ]
        compact_summary = {k: summary[k] for k in display_keys if k in summary}
        # Always use tabulate for summary if rich is False (for test compatibility)
        if not terminal_config.get("rich", True):
            summary_table = [(k, strip_ansi_codes(str(compact_summary[k]))) for k in compact_summary]
            return tabulate(
                summary_table,
                headers=["Metric", "Value"],
                tablefmt="github",
                showindex=False,
            )
        # Otherwise use Rich
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=True, header_style="bold cyan", box=box.ASCII)
            table.add_column("Metric", style="bold")
            table.add_column("Value")
            for k, v in compact_summary.items():
                table.add_row(str(k), str(v))
            panel = Panel(table, title=panel_title, border_style="green")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            summary_table = [(k, compact_summary[k]) for k in compact_summary]
            return tabulate(
                summary_table,
                headers=["Metric", "Value"],
                tablefmt="github",
                showindex=False,
            )
    elif isinstance(summary, list):
        # Fallback: just show the list as a table
        if summary:
            out = tabulate(summary, headers="keys", tablefmt="github", showindex=False)
        else:
            out = "(No data)"
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=False, box=box.ASCII2)
            table.add_row(Text(out, style="cyan"))
            panel = Panel(table, title="[cyan]Summary", border_style="cyan")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return out
    else:
        return str(summary)


def render_slowest_tests(api, section_cfg, terminal_config, return_panel=False):
    test_insights = api.session_dict()
    limit = section_cfg.get("limit", 3)
    # Patch: handle both dict and list for test_insights
    if isinstance(test_insights, dict):
        slowest = test_insights.get("slowest_tests", [])[:limit]
    elif isinstance(test_insights, list):
        slowest = test_insights[:limit]
    else:
        slowest = []
    if slowest:
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=True, header_style="bold magenta", box=box.ASCII2)
            for k in slowest[0].keys():
                table.add_column(str(k), style="yellow")
            for row in slowest:
                table.add_row(*[str(row[k]) for k in row])
            panel = Panel(table, title="[magenta]Slowest Tests", border_style="magenta")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return tabulate(slowest, headers="keys", tablefmt="github", showindex=False)
    else:
        headers = ["Test", "Duration"]
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=True, header_style="bold magenta", box=box.ASCII2)
            for h in headers:
                table.add_column(h, style="yellow")
            table.add_row("(No data)", "-")
            panel = Panel(table, title="[magenta]Slowest Tests", border_style="magenta")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return tabulate(
                [["(No data)", "-"]],
                headers=headers,
                tablefmt="github",
                showindex=False,
            )


def render_unreliable_tests(api, section_cfg, terminal_config, return_panel=False):
    test_insights = api.session_dict()
    # Fallback for DummyAPI in tests
    if isinstance(test_insights, dict):
        least_reliable = test_insights.get("unreliable_tests")
        if least_reliable is None and hasattr(api, "_unreliable"):
            least_reliable = getattr(api, "_unreliable", [])
        else:
            least_reliable = least_reliable or []
    elif isinstance(test_insights, list):
        least_reliable = test_insights
    else:
        least_reliable = []
    limit = section_cfg.get("limit", 3)
    columns = section_cfg.get("columns", ["nodeid", "reliability", "runs", "failures", "unreliable_rate"])
    least_reliable = least_reliable[:limit]
    if least_reliable:
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=True, header_style="bold red", box=box.ASCII2)
            for c in columns:
                table.add_column(str(c), style="yellow")
            for row in least_reliable:
                table.add_row(*[str(row.get(c, "")) for c in columns])
            panel = Panel(table, title="[red]Least Reliable Tests", border_style="red")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return tabulate(least_reliable, headers=columns, tablefmt="github", showindex=False)
    else:
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=True, header_style="bold red", box=box.ASCII2)
            for h in columns:
                table.add_column(h, style="yellow")
            table.add_row("(No data)", "-")
            panel = Panel(table, title="[red]Least Reliable Tests", border_style="red")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return (
                tabulate(
                    [{c: "" for c in columns}],
                    headers=columns,
                    tablefmt="github",
                    showindex=False,
                )
                + "\n(No data)"
            )


def render_trends(api, section_cfg, terminal_config, return_panel=False):
    trend_insights = api.session_dict()
    if isinstance(trend_insights, dict):
        duration_trends = trend_insights.get("duration_trends", {}).get("avg_duration_by_day", {})
        failure_trends = trend_insights.get("failure_trends", {}).get("failures_by_day", {})
    elif isinstance(trend_insights, list):
        duration_trends = {}
        failure_trends = {}
    else:
        duration_trends = {}
        failure_trends = {}
    trend_lines = []
    for trend_name, values in {
        "avg_duration": duration_trends,
        "failures": failure_trends,
    }.items():
        if isinstance(values, dict):
            series = list(values.values())
        elif isinstance(values, (list, tuple)):
            series = values
        else:
            series = []
        line = f"{trend_name}: {sparklines(series)[0] if series else '(no data)'}"
        trend_lines.append(line)
    if terminal_config.get("rich", True) and RICH_AVAILABLE:
        table = Table(show_header=False, box=box.ASCII2)
        for line in trend_lines:
            table.add_row(Text(line, style="cyan"))
        panel = Panel(table, title="[cyan]Trends", border_style="cyan")
        if return_panel:
            return panel
        buffer = io.StringIO()
        console = Console(record=True, force_terminal=True, file=buffer)
        console.print(panel)
        return buffer.getvalue()
    else:
        return "\n".join(trend_lines)


# --- BEGIN: Additional Section Renderers for All Facets ---
def render_session(api, section_cfg, terminal_config, return_panel=False):
    session = api.session_dict()
    if isinstance(session, dict):
        display_keys = section_cfg.get("fields") or list(session.keys())
        compact = {k: session.get(k, "") for k in display_keys}
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=True, header_style="bold blue", box=box.ASCII2)
            table.add_column("Metric", style="bold")
            table.add_column("Value")
            for k, v in compact.items():
                table.add_row(str(k), str(v))
            panel = Panel(table, title="[blue]Session", border_style="blue")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return tabulate(
                list(compact.items()),
                headers=["Metric", "Value"],
                tablefmt="github",
                showindex=False,
            )
    elif isinstance(session, list):
        # Fallback: just show the list as a table
        if session:
            out = tabulate(session, headers="keys", tablefmt="github", showindex=False)
        else:
            out = "(No data)"
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=False, box=box.ASCII2)
            table.add_row(Text(out, style="blue"))
            panel = Panel(table, title="[blue]Session", border_style="blue")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return out
    else:
        return str(session)


def render_test(api, section_cfg, terminal_config, return_panel=False):
    test_insights = api.session_dict()
    if isinstance(test_insights, dict):
        # Show unreliable_tests and slowest_tests as example
        unreliable = test_insights.get("unreliable_tests", [])
        slowest = test_insights.get("slowest_tests", [])
        lines = []
        if unreliable:
            lines.append("Unreliable:")
            lines.append(tabulate(unreliable, headers="keys", tablefmt="github", showindex=False))
        if slowest:
            lines.append("Slowest:")
            lines.append(tabulate(slowest, headers="keys", tablefmt="github", showindex=False))
        out = "\n".join(lines)
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=False, box=box.ASCII2)
            for line in lines:
                table.add_row(Text(line, style="yellow"))
            panel = Panel(table, title="[yellow]Test", border_style="yellow")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return out
    elif isinstance(test_insights, list):
        # Fallback: just show the list as a table
        if test_insights:
            out = tabulate(test_insights, headers="keys", tablefmt="github", showindex=False)
        else:
            out = "(No data)"
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=False, box=box.ASCII2)
            table.add_row(Text(out, style="yellow"))
            panel = Panel(table, title="[yellow]Test", border_style="yellow")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return out
    else:
        return str(test_insights)


def render_trend(api, section_cfg, terminal_config, return_panel=False):
    api.session_dict()
    # Reuse render_trends for now
    return render_trends(api, section_cfg, terminal_config, return_panel)


def render_compare(api, section_cfg, terminal_config, return_panel=False):
    comp_insights = api.session_dict()
    if isinstance(comp_insights, dict):
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=False, box=box.ASCII2)
            table.add_row(Text(str(comp_insights), style="magenta"))
            panel = Panel(table, title="[magenta]Compare", border_style="magenta")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return str(comp_insights)
    elif isinstance(comp_insights, list):
        # Fallback: just show the list as a table
        if comp_insights:
            out = tabulate(comp_insights, headers="keys", tablefmt="github", showindex=False)
        else:
            out = "(No data)"
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=False, box=box.ASCII2)
            table.add_row(Text(out, style="magenta"))
            panel = Panel(table, title="[magenta]Compare", border_style="magenta")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return out
    else:
        return str(comp_insights)


def render_predictive(api, section_cfg, terminal_config, return_panel=False):
    pred_insights = api.session_dict()
    if isinstance(pred_insights, dict):
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=False, box=box.ASCII2)
            table.add_row(Text(str(pred_insights), style="red"))
            panel = Panel(table, title="[red]Predictive", border_style="red")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return str(pred_insights)
    elif isinstance(pred_insights, list):
        # Fallback: just show the list as a table
        if pred_insights:
            out = tabulate(pred_insights, headers="keys", tablefmt="github", showindex=False)
        else:
            out = "(No data)"
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=False, box=box.ASCII2)
            table.add_row(Text(out, style="red"))
            panel = Panel(table, title="[red]Predictive", border_style="red")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return out
    else:
        return str(pred_insights)


def render_meta(api, section_cfg, terminal_config, return_panel=False):
    meta_insights = api.session_dict()
    if isinstance(meta_insights, dict):
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=False, box=box.ASCII2)
            table.add_row(Text(str(meta_insights), style="cyan"))
            panel = Panel(table, title="[cyan]Meta", border_style="cyan")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return str(meta_insights)
    elif isinstance(meta_insights, list):
        # Fallback: just show the list as a table
        if meta_insights:
            out = tabulate(meta_insights, headers="keys", tablefmt="github", showindex=False)
        else:
            out = "(No data)"
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=False, box=box.ASCII2)
            table.add_row(Text(out, style="cyan"))
            panel = Panel(table, title="[cyan]Meta", border_style="cyan")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return out
    else:
        return str(meta_insights)


def render_temporal(api, section_cfg, terminal_config, return_panel=False):
    temporal_insights = api.session_dict()
    if isinstance(temporal_insights, dict):
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=False, box=box.ASCII2)
            table.add_row(Text(str(temporal_insights), style="blue"))
            panel = Panel(table, title="[blue]Temporal", border_style="blue")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return str(temporal_insights)
    elif isinstance(temporal_insights, list):
        # Fallback: just show the list as a table
        if temporal_insights:
            out = tabulate(temporal_insights, headers="keys", tablefmt="github", showindex=False)
        else:
            out = "(No data)"
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=False, box=box.ASCII2)
            table.add_row(Text(out, style="blue"))
            panel = Panel(table, title="[blue]Temporal", border_style="blue")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return out
    else:
        return str(temporal_insights)


# --- END: Additional Section Renderers for All Facets ---

SECTION_RENDERERS = {
    "summary": render_summary,
    "slowest_tests": render_slowest_tests,
    "unreliable_tests": render_unreliable_tests,
    "trends": render_trends,
    # Add all facet/insight renderers:
    "session": render_session,
    "test": render_test,
    "trend": render_trend,
    "compare": render_compare,
    "predictive": render_predictive,
    "meta": render_meta,
    "temporal": render_temporal,
}


def render_insights_in_terminal(api, terminal_config):
    """
    Render terminal output using config-driven, adaptive layout.
    Each section is a panel; panels are packed horizontally if Rich is enabled and available.
    Config options:
      - columns: max panels per row (default: 2)
      - min_panel_width: minimum width per panel (default: 36)
      - width: preferred total width (default: detected terminal width or 88)
    """
    width = terminal_config.get("width")
    if width is None:
        width = shutil.get_terminal_size((88, 20)).columns
    else:
        width = int(width)
    int(terminal_config.get("min_panel_width", 36))
    max_columns = int(terminal_config.get("columns", 2))
    sections = terminal_config.get("sections", ["summary", "slowest_tests", "unreliable_tests", "trends"])
    insights = terminal_config.get("insights", {})
    panels = []
    if terminal_config.get("rich", True) and RICH_AVAILABLE:
        rich_panels = []
        for section in sections:
            section_cfg = insights.get(section, {})
            show = section_cfg.get("show", True)
            if not show:
                continue
            render_fn = SECTION_RENDERERS.get(section)
            if render_fn:
                panel_obj = render_fn(api, section_cfg, terminal_config, return_panel=True)
                rich_panels.append(panel_obj)
            else:
                from rich.panel import Panel

                rich_panels.append(
                    Panel(
                        f"{section.replace('_', ' ').title()}\n(Not implemented)",
                        title=section.title(),
                    )
                )
        output = []
        for i in range(0, len(rich_panels), max_columns):
            row = Columns(rich_panels[i : i + max_columns], expand=True, equal=True)
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(row)
            output.append(buffer.getvalue())
        return "\n".join(output)
    else:
        for section in sections:
            section_cfg = insights.get(section, {})
            show = section_cfg.get("show", True)
            if not show:
                continue
            render_fn = SECTION_RENDERERS.get(section)
            if render_fn:
                panel = render_fn(api, section_cfg, terminal_config)
                panels.append(f"{section.replace('_', ' ').title()}:\n{panel}")
            else:
                panels.append(f"{section.replace('_', ' ').title()}:\n(Not implemented)")
        return "\n\n".join(panels)
