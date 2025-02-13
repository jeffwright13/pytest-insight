import pytest


def pytest_addoption(parser):
    """Add pytest-insight specific command line options."""
    group = parser.getgroup("insight")
    group.addoption(
        "--insight",
        action="store_true",
        default=False,
        help="Enable pytest-insight plugin for test history analysis",
    )


@pytest.hookimpl
def pytest_configure(config):
    """Configure the plugin if enabled."""
    if config.getoption("insight"):
        # Create and register the plugin instance
        insight = PytestInsight(config)
        config.pluginmanager.register(insight, "pytest-insight")


class PytestInsight:
    """Main plugin class for pytest-insight."""

    def __init__(self, config):
        self.config = config
