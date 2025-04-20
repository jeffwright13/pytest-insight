"""
Tests for pytest_insight.config (terminal config loader and enable/disable logic).
"""
import textwrap

from pytest_insight import config as insight_config

TERMINAL_TOML = textwrap.dedent(
    """
[terminal]
enabled = true
sections = ["summary", "unreliable_tests"]

[terminal.insights.summary]
show = true
fields = ["total_sessions", "pass_rate"]

[terminal.insights.unreliable_tests]
show = false
limit = 3
columns = ["nodeid", "reliability"]
"""
)


def test_load_terminal_config_from_file(tmp_path):
    cfg_file = tmp_path / "pytest-insight.toml"
    cfg_file.write_text(TERMINAL_TOML)
    config = insight_config.load_terminal_config(str(cfg_file))
    assert config["enabled"] is True
    assert config["sections"] == ["summary", "unreliable_tests"]
    assert config["insights"]["summary"]["show"] is True
    assert config["insights"]["summary"]["fields"] == ["total_sessions", "pass_rate"]
    assert config["insights"]["unreliable_tests"]["show"] is False
    assert config["insights"]["unreliable_tests"]["limit"] == 3
    assert config["insights"]["unreliable_tests"]["columns"] == ["nodeid", "reliability"]


def test_terminal_output_enabled_respects_env(monkeypatch):
    cfg = {"enabled": True}
    monkeypatch.setenv("PYTEST_INSIGHT_TERMINAL", "0")
    assert not insight_config.terminal_output_enabled(cfg)
    monkeypatch.setenv("PYTEST_INSIGHT_TERMINAL", "false")
    assert not insight_config.terminal_output_enabled(cfg)
    monkeypatch.setenv("PYTEST_INSIGHT_TERMINAL", "no")
    assert not insight_config.terminal_output_enabled(cfg)
    monkeypatch.delenv("PYTEST_INSIGHT_TERMINAL", raising=False)
    assert insight_config.terminal_output_enabled(cfg)


def test_terminal_output_enabled_respects_config(monkeypatch):
    monkeypatch.delenv("PYTEST_INSIGHT_TERMINAL", raising=False)
    assert insight_config.terminal_output_enabled({"enabled": True})
    assert not insight_config.terminal_output_enabled({"enabled": False})


def test_load_terminal_config_defaults(tmp_path, monkeypatch):
    # No config file: should use defaults
    monkeypatch.chdir(tmp_path)
    config = insight_config.load_terminal_config()
    assert config["sections"]
    assert config["insights"]["summary"]["show"] is True
    assert config["enabled"] is True
