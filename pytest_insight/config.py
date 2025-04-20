"""
Config loader for pytest-insight dashboard and UI settings (TOML-based).
Supports Python 3.7+ (uses tomli for <3.11, tomllib for >=3.11).
"""
import os
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

_DEFAULT_CONFIG = {
    "dashboard": {
        "sections": ["summary", "slowest_tests", "unreliable_tests", "trends"],
        "insights": {
            "summary": {"show": True, "fields": ["total_sessions", "total_tests", "pass_rate", "fail_rate"]},
            "slowest_tests": {"show": True, "limit": 5},
            "unreliable_tests": {"show": True, "limit": 5, "columns": ["nodeid", "reliability", "runs", "failures"]},
            "trends": {"show": True, "types": ["duration", "failures"]},
        },
        "formatting": {
            "table_format": "github",
            "width": "auto",
            "color": True,
            "compact": True,
            "max_table_rows": 20,
        },
    }
}

_DEFAULT_TERMINAL_CONFIG = {
    "enabled": True,
    "sections": ["summary", "slowest_tests", "unreliable_tests", "trends"],
    "insights": {
        "summary": {"show": True, "fields": ["total_sessions", "total_tests", "pass_rate", "fail_rate"]},
        "slowest_tests": {"show": True, "limit": 5},
        "unreliable_tests": {"show": True, "limit": 5, "columns": ["nodeid", "reliability", "runs", "failures"]},
        "trends": {"show": True, "types": ["duration", "failures"]},
    },
}


def find_config_path():
    """
    Returns the first found config path in the following order:
    1. Directory containing pytest_insight package (__file__)
    2. Current working directory
    3. User home directory
    """
    candidates = [
        os.path.join(os.path.dirname(__file__), "pytest_insight_dashboard.toml"),
        os.path.join(os.getcwd(), "pytest_insight_dashboard.toml"),
        os.path.expanduser("~/.pytest_insight_dashboard.toml"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def load_dashboard_config(path: str = None) -> dict:
    """
    Loads the dashboard config from a TOML file. Returns a dict with config values,
    or sensible defaults if the file does not exist or is invalid.
    Search order: package dir, cwd, user home.
    """
    config_path = path or find_config_path()
    if not config_path:
        return _DEFAULT_CONFIG
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"[pytest-insight] Failed to load config: {e}\nUsing defaults.")
        return _DEFAULT_CONFIG


def load_terminal_config(path: str = None) -> dict:
    """
    Loads the [terminal] config from the TOML file. Returns a dict with config values,
    or sensible defaults if the section does not exist.
    """
    config_path = path or find_config_path()
    if not config_path:
        return _DEFAULT_TERMINAL_CONFIG
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        # Support both flat [terminal] and nested [terminal.insights.*] keys
        terminal = config.get("terminal", {})
        # If missing, fall back to defaults
        if not terminal:
            return _DEFAULT_TERMINAL_CONFIG
        # Merge in insights if present
        insights = {}
        for key in ("summary", "slowest_tests", "unreliable_tests", "trends"):
            insight_key = f"terminal.insights.{key}"
            if insight_key in config:
                insights[key] = config[insight_key]
        if insights:
            terminal["insights"] = insights
        return terminal
    except Exception as e:
        print(f"[pytest-insight] Failed to load terminal config: {e}\nUsing defaults.")
        return _DEFAULT_TERMINAL_CONFIG


def terminal_output_enabled(terminal_config: dict = None) -> bool:
    """
    Returns True if terminal output is enabled, considering both config and environment variable.
    Env var PYTEST_INSIGHT_TERMINAL=0 or false disables output regardless of config.
    """
    import os

    env = os.getenv("PYTEST_INSIGHT_TERMINAL")
    if env is not None and env.lower() in ("0", "false", "no"):  # explicit disable
        return False
    if terminal_config is None:
        from .config import load_terminal_config

        terminal_config = load_terminal_config()
    return terminal_config.get("enabled", True)
