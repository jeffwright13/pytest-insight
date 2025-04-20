"""
Tests for the adaptive, config-driven terminal layout manager in terminal_output.py.
"""
import textwrap
import types
import re
from pytest_insight.utils.terminal_output import render_insights_in_terminal

ANSI_BOLD = '\033[1m'
ANSI_RED = '\033[31m'
ANSI_RESET = '\033[0m'

class DummyAPI:
    def __init__(self, summary=None, slowest=None, unreliable=None, trends=None):
        self._summary = summary or {}
        self._slowest = slowest or []
        self._unreliable = unreliable or []
        self._trends = trends or {}
    def session(self):
        return types.SimpleNamespace(insight=lambda kind: self._summary)
    def test(self):
        return types.SimpleNamespace(insight=lambda kind: {
            "slowest_tests": self._slowest,
            "unreliable_tests": self._unreliable,
        })
    def trend(self):
        return types.SimpleNamespace(insight=lambda kind: self._trends)

def make_panel(label, width=20, height=4):
    line = label.center(width, '-')
    return '\n'.join([line] * height)

def make_ansi_panel(label, width=20, height=4, color=None, bold=False):
    line = label.center(width, '-')
    if color:
        line = color + line + ANSI_RESET
    if bold:
        line = ANSI_BOLD + line + ANSI_RESET
    return '\n'.join([line] * height)

def strip_ansi(s):
    return re.sub(r'\x1b\[[0-9;]*m', '', s)

def test_pack_panels_horizontal(monkeypatch):
    # Simulate two panels, each 20 wide, total 44 with gap
    from pytest_insight.utils.terminal_output import pack_panels_horizontally
    panels = [make_panel("A", 20), make_panel("B", 20)]
    result = pack_panels_horizontally(panels, max_width=44, gap=4)
    # Should be side by side
    assert result.count('A') > 0 and result.count('B') > 0
    assert '\n\n' not in result  # not stacked

def test_pack_panels_vertical(monkeypatch):
    from pytest_insight.utils.terminal_output import pack_panels_horizontally
    panels = [make_panel("A", 20), make_panel("B", 20)]
    result = pack_panels_horizontally(panels, max_width=30, gap=4)
    # Should be stacked
    assert result.splitlines().count('---------A----------') == 4
    assert result.splitlines().count('---------B----------') == 4
    assert '\n\n' in result or result.count('A') == 4

def test_pack_panels_three_columns(monkeypatch):
    from pytest_insight.utils.terminal_output import pack_panels_horizontally
    panels = [make_panel(f"P{i+1}", 12) for i in range(3)]
    result = pack_panels_horizontally(panels, max_width=44, gap=2)
    # All three should be on the same row
    assert result.count('P1') > 0 and result.count('P2') > 0 and result.count('P3') > 0
    assert '\n\n' not in result

def test_pack_panels_ansi(monkeypatch):
    from pytest_insight.utils.terminal_output import pack_panels_horizontally
    panels = [make_ansi_panel("A", 16, color=ANSI_RED), make_ansi_panel("B", 16, bold=True)]
    result = pack_panels_horizontally(panels, max_width=40, gap=4)
    # Should contain ANSI codes
    assert ANSI_RED in result or ANSI_BOLD in result
    # Stripped version should still align
    stripped = strip_ansi(result)
    lines = stripped.splitlines()
    assert all(len(line) == len(lines[0]) for line in lines if line.strip())
    assert 'A' in stripped and 'B' in stripped

def test_render_insights_in_terminal_adaptive(monkeypatch):
    # Simulate a wide terminal (60 chars), should pack 2 panels
    summary = {"total_sessions": 3, "total_tests": 30, "pass_rate": 0.9, "fail_rate": 0.1}
    slowest = [{"nodeid": "t1", "duration": 1.5}, {"nodeid": "t2", "duration": 1.2}]
    unreliable = [{"nodeid": "t1", "reliability": 0.7, "runs": 10, "failures": 3}]
    api = DummyAPI(summary, slowest, unreliable)
    config = {"sections": ["summary", "slowest_tests", "unreliable_tests"], "columns": 2, "width": 60}
    out = render_insights_in_terminal(api, config)
    # Should contain both summary and slowest on the same row
    assert "Summary:" in out and "Slowest Tests:" in out

def test_render_insights_in_terminal_config_driven(monkeypatch):
    # Only show unreliable_tests
    unreliable = [{"nodeid": "t1", "reliability": 0.7, "runs": 10, "failures": 3}]
    api = DummyAPI({}, [], unreliable)
    config = {"sections": ["unreliable_tests"], "columns": 1, "width": 40}
    out = render_insights_in_terminal(api, config)
    assert "Least Reliable Tests:" in out
    assert "t1" in out
    assert "Summary:" not in out
    assert "Slowest Tests:" not in out

def test_render_insights_in_terminal_min_panel_width(monkeypatch):
    # Panels too wide for 2 columns, should stack
    summary = {"a": 1}
    api = DummyAPI(summary, [], [])
    config = {"sections": ["summary"] * 2, "columns": 2, "width": 30, "min_panel_width": 28}
    out = render_insights_in_terminal(api, config)
    # Only one panel per row
    assert out.count('Summary:') == 2
    assert '\n\n' in out

def test_render_insights_in_terminal_with_ansi(monkeypatch):
    # Simulate a section with ANSI codes (e.g., for color)
    class AnsiAPI(DummyAPI):
        def session(self):
            return types.SimpleNamespace(insight=lambda kind: {"total_sessions": f"{ANSI_BOLD}5{ANSI_RESET}"})
    api = AnsiAPI()
    config = {"sections": ["summary"], "columns": 1, "width": 40}
    out = render_insights_in_terminal(api, config)
    # Should contain ANSI bold
    assert ANSI_BOLD in out
    # Stripped should still show the number
    assert '5' in strip_ansi(out)

def test_pack_panels_empty(monkeypatch):
    from pytest_insight.utils.terminal_output import pack_panels_horizontally
    panels = []
    result = pack_panels_horizontally(panels, max_width=40, gap=4)
    assert result == ''

def test_pack_panels_mixed_ansi(monkeypatch):
    from pytest_insight.utils.terminal_output import pack_panels_horizontally
    panels = [make_panel("PLAIN", 12), make_ansi_panel("BOLD", 12, bold=True)]
    result = pack_panels_horizontally(panels, max_width=32, gap=4)
    # One panel plain, one with ANSI
    assert 'PLAIN' in result and 'BOLD' in result
    assert ANSI_BOLD in result
    # Stripped should still align
    stripped = strip_ansi(result)
    lines = stripped.splitlines()
    assert all(len(line) == len(lines[0]) for line in lines if line.strip())

def test_pack_panels_long_short(monkeypatch):
    from pytest_insight.utils.terminal_output import pack_panels_horizontally
    long_label = "LONG_LABEL_PANEL" * 4
    short_label = "S"
    panels = [make_panel(long_label, 40), make_panel(short_label, 3)]
    result = pack_panels_horizontally(panels, max_width=100, gap=4)
    # Both present, lines align
    assert long_label in result and short_label in result
    lines = result.splitlines()
    assert all(len(line) == len(lines[0]) for line in lines if line.strip())

def test_render_insights_in_terminal_empty_sections(monkeypatch):
    api = DummyAPI()
    config = {"sections": [], "columns": 2, "width": 40}
    out = render_insights_in_terminal(api, config)
    assert out == ''

def test_render_insights_in_terminal_long_label(monkeypatch):
    long_label = "X" * 60
    class LongLabelAPI(DummyAPI):
        def session(self):
            return types.SimpleNamespace(insight=lambda kind: {"total_sessions": long_label})
    api = LongLabelAPI()
    config = {"sections": ["summary"], "columns": 1, "width": 80}
    out = render_insights_in_terminal(api, config)
    assert long_label in out
    # Should not be truncated
    assert len(max(out.splitlines(), key=len)) >= 60

def test_render_insights_in_terminal_short_label(monkeypatch):
    short_label = "Y"
    class ShortLabelAPI(DummyAPI):
        def session(self):
            return types.SimpleNamespace(insight=lambda kind: {"total_sessions": short_label})
    api = ShortLabelAPI()
    config = {"sections": ["summary"], "columns": 1, "width": 20}
    out = render_insights_in_terminal(api, config)
    assert short_label in out
    # Should appear in a value row between pipes (tabulate style)
    lines = out.splitlines()
    value_lines = [line for line in lines if short_label in line]
    assert any(line.startswith('|') and line.endswith('|') and 'Y' in line for line in value_lines)
