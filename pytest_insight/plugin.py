from datetime import datetime, timezone

import pytest
from pytest_oof.plugin import ResultsFromConfig
from pytest_oof.utils import Results


def pytest_addoption(parser):
    """Add pytest-insight command line options."""
    group = parser.getgroup("insight")
    group.addoption(
        "--insight",
        action="store_true",
        default=False,
        help="Enable pytest-insight plugin for test history analysis",
    )

    parser.addini(
        "insight",
        type="bool",
        help="Enable the insight plugin, providing test history analysis",
        default=False,
    )


@pytest.hookimpl
def pytest_configure(config):
    """Configure the plugin if enabled."""
    if config.getoption("insight"):
        # Enable pytest-oof automatically
        config.option.oof = True
        # Create and register our plugin instance
        insight = PytestInsight(config)
        config.pluginmanager.register(insight, "pytest-insight")


class PytestInsight:
    """Main plugin class for pytest-insight."""

    def __init__(self, config):
        self.config = config
        self.results = None

    def process_results(self, results):
        """Process the pytest-oof Results object."""
        pass
        # json_data = results.to_json()
        # print(f"Processing test results with insight: {json_data}")
        # setattr(results, "insight_data", json_data)

    @pytest.hookimpl
    def pytest_oof_results(self, results):
        """Hook called by pytest-oof after results processing."""
        self.results = results
        self.process_results(results)

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        """Hook to perform final processing after test session."""
        if self.results is None:
            print("No results received from pytest-oof.")
