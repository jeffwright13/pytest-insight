"""
Dashboard formatter for pytest-insight terminal output.
Formats summary tables, test insights, and sparklines for trends.
"""
import io
import shutil
import sys
from typing import Any

from sparklines import sparklines
from tabulate import tabulate

from pytest_insight.insight_api import InsightAPI

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

def sparkline(data: Any) -> str:
    return ''.join(sparklines(data)) if data else ""


def render_summary(api, section_cfg, terminal_config, return_panel=False):
    summary_obj = api.session().insight("summary")
    summary = summary_obj.as_dict() if hasattr(summary_obj, "as_dict") else summary_obj

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

    if isinstance(summary, dict):
        display_keys = section_cfg.get('fields')
        if not display_keys:
            display_keys = [
                k for k in [
                    "total_sessions", "total_tests", "pass_rate", "fail_rate", "avg_duration", "median_duration", "min_duration", "max_duration"
                ] if k in summary
            ]
        compact_summary = {k: summary[k] for k in display_keys if k in summary}
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=True, header_style="bold cyan", box=box.ASCII2)
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
            return tabulate(summary_table, headers=["Metric", "Value"], tablefmt="github", showindex=False)
    else:
        return str(summary)


def render_slowest_tests(api, section_cfg, terminal_config, return_panel=False):
    test_insights = api.test().insight("detailed")
    limit = section_cfg.get('limit', 3)
    slowest = test_insights.get("slowest_tests", [])[:limit]
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
            return tabulate([["(No data)", "-"]], headers=headers, tablefmt="github", showindex=False)

def render_unreliable_tests(api, section_cfg, terminal_config, return_panel=False):
    test_insights = api.test().insight("detailed")
    limit = section_cfg.get('limit', 3)
    columns = section_cfg.get('columns', ["nodeid", "reliability", "runs", "failures", "unreliable_rate"])
    least_reliable = test_insights.get("unreliable_tests", [])[:limit]
    table_data = [
        {k: d.get(k, "") for k in columns}
        for d in least_reliable
    ] if least_reliable else []
    if table_data:
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=True, header_style="bold red", box=box.ASCII2)
            for col in columns:
                table.add_column(str(col), style="yellow")
            for row in table_data:
                table.add_row(*[str(row[k]) for k in columns])
            panel = Panel(table, title="[red]Least Reliable Tests", border_style="red")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return tabulate(table_data, headers="keys", tablefmt="github", showindex=False)
    else:
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=True, header_style="bold red", box=box.ASCII2)
            for col in columns:
                table.add_column(str(col), style="yellow")
            table.add_row(*["(No data)" if i == 0 else "-" for i in range(len(columns))])
            panel = Panel(table, title="[red]Least Reliable Tests", border_style="red")
            if return_panel:
                return panel
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(panel)
            return buffer.getvalue()
        else:
            return tabulate([{c: "" for c in columns}], headers=columns, tablefmt="github", showindex=False) + "\n(No data)"

def render_trends(api, section_cfg, terminal_config, return_panel=False):
    trend_insights = api.trend().insight("trend")
    duration_trends = trend_insights.get("duration_trends", {}).get("avg_duration_by_day", {})
    failure_trends = trend_insights.get("failure_trends", {}).get("failures_by_day", {})
    trend_lines = []
    for trend_name, values in {"avg_duration": duration_trends, "failures": failure_trends}.items():
        if isinstance(values, dict):
            series = list(values.values())
        elif isinstance(values, (list, tuple)):
            series = values
        else:
            series = [values]
        line = f"{trend_name}: {sparkline(series)}  ({series[-1] if series else ''})"
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
    session_obj = api.session().insight("health")
    session = session_obj if isinstance(session_obj, dict) else getattr(session_obj, "as_dict", lambda: session_obj)()
    if isinstance(session, dict):
        display_keys = section_cfg.get('fields') or list(session.keys())
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
            return tabulate(list(compact.items()), headers=["Metric", "Value"], tablefmt="github", showindex=False)
    else:
        return str(session)

def render_test(api, section_cfg, terminal_config, return_panel=False):
    test_obj = api.test().insight("detailed")
    if isinstance(test_obj, dict):
        # Show unreliable_tests and slowest_tests as example
        unreliable = test_obj.get("unreliable_tests", [])
        slowest = test_obj.get("slowest_tests", [])
        lines = []
        if unreliable:
            lines.append("Unreliable:")
            lines.append(tabulate(unreliable, headers="keys", tablefmt="github", showindex=False))
        if slowest:
            lines.append("Slowest:")
            lines.append(tabulate(slowest, headers="keys", tablefmt="github", showindex=False))
        if not lines:
            lines.append("No test-level data.")
        out = "\n".join(lines)
        if terminal_config.get("rich", True) and RICH_AVAILABLE:
            table = Table(show_header=False, box=box.ASCII2)
            for l in lines:
                table.add_row(Text(l, style="yellow"))
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
        return str(test_obj)

def render_trend(api, section_cfg, terminal_config, return_panel=False):
    trend_obj = api.trend().insight("trend")
    # Reuse render_trends for now
    return render_trends(api, section_cfg, terminal_config, return_panel)

def render_compare(api, section_cfg, terminal_config, return_panel=False):
    comp_obj = api.compare().insight("regression")
    if terminal_config.get("rich", True) and RICH_AVAILABLE:
        table = Table(show_header=False, box=box.ASCII2)
        table.add_row(Text(str(comp_obj), style="magenta"))
        panel = Panel(table, title="[magenta]Compare", border_style="magenta")
        if return_panel:
            return panel
        buffer = io.StringIO()
        console = Console(record=True, force_terminal=True, file=buffer)
        console.print(panel)
        return buffer.getvalue()
    else:
        return str(comp_obj)

def render_predictive(api, section_cfg, terminal_config, return_panel=False):
    pred_obj = api.predictive().insight("predictive_failure")
    if terminal_config.get("rich", True) and RICH_AVAILABLE:
        table = Table(show_header=False, box=box.ASCII2)
        table.add_row(Text(str(pred_obj), style="red"))
        panel = Panel(table, title="[red]Predictive", border_style="red")
        if return_panel:
            return panel
        buffer = io.StringIO()
        console = Console(record=True, force_terminal=True, file=buffer)
        console.print(panel)
        return buffer.getvalue()
    else:
        return str(pred_obj)

def render_meta(api, section_cfg, terminal_config, return_panel=False):
    meta_obj = api.meta().insight("meta")
    if terminal_config.get("rich", True) and RICH_AVAILABLE:
        table = Table(show_header=False, box=box.ASCII2)
        table.add_row(Text(str(meta_obj), style="cyan"))
        panel = Panel(table, title="[cyan]Meta", border_style="cyan")
        if return_panel:
            return panel
        buffer = io.StringIO()
        console = Console(record=True, force_terminal=True, file=buffer)
        console.print(panel)
        return buffer.getvalue()
    else:
        return str(meta_obj)

def render_temporal(api, section_cfg, terminal_config, return_panel=False):
    temporal_obj = api.temporal().insight("trend")
    if terminal_config.get("rich", True) and RICH_AVAILABLE:
        table = Table(show_header=False, box=box.ASCII2)
        table.add_row(Text(str(temporal_obj), style="blue"))
        panel = Panel(table, title="[blue]Temporal", border_style="blue")
        if return_panel:
            return panel
        buffer = io.StringIO()
        console = Console(record=True, force_terminal=True, file=buffer)
        console.print(panel)
        return buffer.getvalue()
    else:
        return str(temporal_obj)
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
    width = terminal_config.get('width')
    if width is None:
        width = shutil.get_terminal_size((88, 20)).columns
    else:
        width = int(width)
    min_panel_width = int(terminal_config.get('min_panel_width', 36))
    max_columns = int(terminal_config.get('columns', 2))
    sections = terminal_config.get('sections', ["summary", "slowest_tests", "unreliable_tests", "trends"])
    insights = terminal_config.get('insights', {})
    panels = []
    if terminal_config.get("rich", True) and RICH_AVAILABLE:
        rich_panels = []
        for section in sections:
            section_cfg = insights.get(section, {})
            show = section_cfg.get('show', True)
            if not show:
                continue
            render_fn = SECTION_RENDERERS.get(section)
            if render_fn:
                panel_obj = render_fn(api, section_cfg, terminal_config, return_panel=True)
                rich_panels.append(panel_obj)
            else:
                from rich.panel import Panel
                rich_panels.append(Panel(f"{section.replace('_', ' ').title()}\n(Not implemented)", title=section.title()))
        output = []
        for i in range(0, len(rich_panels), max_columns):
            row = Columns(rich_panels[i:i+max_columns], expand=True, equal=True)
            buffer = io.StringIO()
            console = Console(record=True, force_terminal=True, file=buffer)
            console.print(row)
            output.append(buffer.getvalue())
        return "\n".join(output)
    else:
        for section in sections:
            section_cfg = insights.get(section, {})
            show = section_cfg.get('show', True)
            if not show:
                continue
            render_fn = SECTION_RENDERERS.get(section)
            if render_fn:
                panel = render_fn(api, section_cfg, terminal_config)
                panels.append(f"{section.replace('_', ' ').title()}:\n{panel}")
            else:
                panels.append(f"{section.replace('_', ' ').title()}:\n(Not implemented)")
        return "\n\n".join(panels)
