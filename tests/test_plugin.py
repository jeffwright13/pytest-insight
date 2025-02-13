from pytest_insight import __version__


def test_version():
    """Verify we can access the package version."""
    assert isinstance(__version__, str)
    assert __version__ != ""


def test_plugin_disabled_by_default(pytestconfig):
    """Verify plugin is not active unless --insight flag is used."""
    plugin = pytestconfig.pluginmanager.get_plugin("pytest-insight")
    assert plugin is None


def test_plugin_enabled_with_flag(tester):
    """Verify plugin is properly registered when --insight flag is used."""
    result = tester.runpytest("--insight")
    # Exit code 4 means 'usage error'
    assert result.ret == 4
    # But the plugin should be loaded
    result.stdout.fnmatch_lines(["*pytest-insight-*"])


def test_help_shows_insight_option(tester):
    """Verify our plugin option appears in pytest help."""
    result = tester.runpytest("--help")
    result.stdout.fnmatch_lines(["*insight:*", "*--insight*Enable pytest-insight plugin for test history analysis*"])
