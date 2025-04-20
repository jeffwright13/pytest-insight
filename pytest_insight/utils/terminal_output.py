"""
Dashboard formatter for pytest-insight terminal output.
Formats summary tables, test insights, and sparklines for trends.
"""
from typing import Any, Dict, List
from pytest_insight.insight_api import InsightAPI
from sparklines import sparklines
from tabulate import tabulate
import shutil


def sparkline(data: List[float]) -> str:
    return ''.join(sparklines(data)) if data else ""


def pack_panels_horizontally(panels, max_width, gap=4):
    """
    Arrange a list of multiline string panels side by side, if space allows.
    Otherwise, stack vertically.
    """
    if not panels:
        return ''
    split_panels = [p.splitlines() for p in panels]
    heights = [len(lines) for lines in split_panels]
    max_height = max(heights)
    padded_panels = [
        lines + [''] * (max_height - len(lines)) for lines in split_panels
    ]
    widths = [max(len(line) for line in lines) for lines in padded_panels]
    total_width = sum(widths) + gap * (len(widths) - 1)
    if total_width > max_width:
        # Stack vertically
        return '\n\n'.join(['\n'.join(lines) for lines in padded_panels])
    lines = []
    for row in range(max_height):
        line = (' ' * gap).join(p[row].ljust(w) for p, w in zip(padded_panels, widths))
        lines.append(line.rstrip())
    return '\n'.join(lines)


def render_insights_in_terminal(api, terminal_config):
    """
    Render terminal output using config-driven, adaptive layout.
    Each section is a panel; panels are packed horizontally if space allows.
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
    # Collect panels
    panels = []
    for section in sections:
        # Find per-section config
        section_cfg = insights.get(section, {})
        show = section_cfg.get('show', True)
        if not show:
            continue
        if section == "summary":
            summary = api.session().insight("health")
            if isinstance(summary, dict):
                display_keys = section_cfg.get('fields')
                if not display_keys:
                    display_keys = [
                        k for k in [
                            "total_sessions", "total_tests", "pass_rate", "fail_rate", "avg_duration", "median_duration", "min_duration", "max_duration"
                        ] if k in summary
                    ]
                compact_summary = {k: summary.get(k, "") for k in display_keys} if display_keys else summary
                panel = tabulate([compact_summary], headers="keys", tablefmt="github") if isinstance(compact_summary, dict) else str(compact_summary)
            else:
                panel = str(summary)
            panels.append("Summary:\n" + panel)
        elif section == "slowest_tests":
            test_insights = api.test().insight("detailed")
            limit = section_cfg.get('limit', 3)
            slowest = test_insights.get("slowest_tests", [])[:limit]
            panel = tabulate(slowest, headers="keys", tablefmt="github") if slowest else "(No data)"
            panels.append("Slowest Tests:\n" + panel)
        elif section == "unreliable_tests":
            test_insights = api.test().insight("detailed")
            limit = section_cfg.get('limit', 3)
            columns = section_cfg.get('columns', ["nodeid", "reliability", "runs", "failures", "unreliable_rate"])
            least_reliable = test_insights.get("unreliable_tests", [])[:limit]
            table_data = [
                {k: d.get(k, "") for k in columns}
                for d in least_reliable
            ] if least_reliable else []
            panel = tabulate(table_data, headers="keys", tablefmt="github") if table_data else "(No data)"
            panels.append("Least Reliable Tests:\n" + panel)
        elif section == "trends":
            trend_insights = api.trend().insight("trend")
            duration_trends = trend_insights.get("duration_trends", {}).get("avg_duration_by_day", {})
            failure_trends = trend_insights.get("failure_trends", {}).get("failures_by_day", {})
            # Sparkline for each trend
            trend_lines = []
            for trend_name, values in {"avg_duration": duration_trends, "failures": failure_trends}.items():
                if isinstance(values, dict):
                    series = list(values.values())
                elif isinstance(values, (list, tuple)):
                    series = values
                else:
                    series = [values]
                trend_lines.append(f"{trend_name}: {sparkline(series)}  ({series[-1] if series else ''})")
            panel = "\n".join(trend_lines)
            panels.append("Trends:\n" + panel)
        # Add more sections as needed
    # Adaptive layout: try to pack as many panels per row as fit, up to max_columns
    output_lines = []
    i = 0
    while i < len(panels):
        row_panels = panels[i:i+max_columns]
        if len(row_panels) == 1 or width // len(row_panels) < min_panel_width:
            # Stack vertically if not enough width
            output_lines.append('\n\n'.join(row_panels))
            i += len(row_panels)
        else:
            output_lines.append(pack_panels_horizontally(row_panels, width, gap=4))
            i += len(row_panels)
    return '\n\n'.join(output_lines)
