import pytest
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
    # Exit code 5 means 'no tests collected' which is expected
    assert result.ret == 5
    # But the plugin should be loaded
    result.stdout.fnmatch_lines(
        [
            "*plugins:*insight-0.1.0*"  # Updated to match actual output
        ]
    )


def test_help_shows_insight_option(tester):
    """Verify our plugin option appears in pytest help."""
    result = tester.runpytest("--help")
    result.stdout.fnmatch_lines(["*insight:*", "*--insight*Enable pytest-insight plugin for test history analysis*"])


def test_plugin_registers_hooks(tester):
    """Test that plugin hooks are registered when enabled."""
    result = tester.runpytest("--insight", "--help")
    # Plugin should be listed in help output
    result.stdout.fnmatch_lines(["*Enable the insight plugin*"])


# def test_oof_results_hook(tester):
#     """Test that pytest_oof_results hook receives and processes results."""
#     # Create a test file with a simple test
#     tester.makepyfile(
#         """
#         def test_example():
#             assert True
#         """
#     )

#     result = tester.runpytest("--insight", "-v")
#     assert result.ret == 0
#     # Should show our plugin received results
#     result.stdout.no_fnmatch_line("*No results received from pytest-oof*")


# def test_process_results_called(tester, mocker):
#     """Test that process_results is called when results are received."""
#     # Create a test file
#     tester.makepyfile(
#         """
#         def test_example():
#             assert True
#         """
#     )

#     # Run with insight enabled
#     result = tester.runpytest("--insight", "-v")
#     assert result.ret == 0


@pytest.mark.parametrize("flag", ["--insight", "--oof"])
def test_plugin_enables_oof(tester, flag):
    """Test that --insight automatically enables pytest-oof."""
    tester.makepyfile(
        """
        def test_example():
            assert True
        """
    )

    result = tester.runpytest(flag, "-v")
    assert result.ret == 0
    # Should see oof plugin in plugins list
    result.stdout.fnmatch_lines(["*oof-*"])
