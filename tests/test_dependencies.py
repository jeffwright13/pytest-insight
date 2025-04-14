"""Tests for dependency structure and CLI behavior with different dependency sets."""

import importlib.util

import pytest

# Core dependencies (should always be available)
CORE_DEPS = ["colorama", "ijson", "prompt_toolkit", "pytest", "rich", "typer"]

# Visualization dependencies (only available with [visualize])
VISUALIZE_DEPS = ["fastapi", "pandas", "plotly", "sklearn", "streamlit", "uvicorn"]


def is_module_available(module_name):
    """Check if a module can be imported."""
    # Handle package names with dashes by converting to underscores
    module_name = module_name.replace("-", "_")
    return importlib.util.find_spec(module_name) is not None


def test_core_dependencies():
    """Test that core dependencies are always available."""
    for dep in CORE_DEPS:
        assert is_module_available(dep), f"Core dependency {dep} not available"


def test_visualization_dependencies():
    """Test visualization dependencies availability based on installation type."""
    # Check if we're in a visualization-enabled environment
    missing_deps = [dep for dep in VISUALIZE_DEPS if not is_module_available(dep)]

    if missing_deps:
        pytest.skip(
            f"Not in visualize environment (missing: {', '.join(missing_deps)}). "
            "Skip this test when running with basic installation."
        )

    # If we're here, all visualization dependencies should be available
    for dep in VISUALIZE_DEPS:
        assert is_module_available(dep), f"Visualization dependency {dep} not available"


def test_cli_core_functionality(tester):
    """Test that core CLI functionality works in any environment."""
    # Create a simple test script that uses the core CLI
    tester.makepyfile(
        test_cli_core="""
        import subprocess
        import sys
        
        def test_profile_command():
            # Run the profile list command
            result = subprocess.run(
                [sys.executable, "-m", "pytest_insight", "profile", "list"],
                capture_output=True,
                text=True
            )
            # Command should succeed
            assert result.returncode == 0
            # Output should contain expected text
            assert "Available storage profiles" in result.stdout
    """
    )

    # Run the test
    result = tester.runpytest("-v", "test_cli_core.py")

    # Check that the test passed
    result.stdout.fnmatch_lines(["*test_profile_command PASSED*"])
    assert result.ret == 0


def test_cli_dashboard_behavior(tester):
    """Test dashboard CLI behavior based on installation environment."""
    # Create a test script that tries to use the dashboard
    tester.makepyfile(
        test_cli_dashboard="""
        import subprocess
        import sys
        import importlib.util
        
        def test_dashboard_command():
            # Check if we're in a visualization environment
            has_streamlit = importlib.util.find_spec("streamlit") is not None
            
            # Run the dashboard command with --help to avoid actually launching it
            result = subprocess.run(
                [sys.executable, "-m", "pytest_insight", "dashboard", "launch", "--help"],
                capture_output=True,
                text=True
            )
            
            combined_output = result.stdout + result.stderr
            
            if has_streamlit:
                # In visualization environment, command should succeed
                assert result.returncode == 0
                assert "Launch the pytest-insight web dashboard" in combined_output
            else:
                # In basic environment, should show helpful error about missing dependencies
                # The command might still return 0 with --help, so we check the output
                assert "Missing required dependencies" in combined_output or result.returncode != 0
                assert "pytest-insight[visualize]" in combined_output
    """
    )

    # Run the test
    result = tester.runpytest("-v", "test_cli_dashboard.py")

    # Check that the test ran (it should pass in either environment)
    result.stdout.fnmatch_lines(["*test_dashboard_command PASSED*"])
    assert result.ret == 0


def test_cli_api_explorer_behavior(tester):
    """Test API Explorer CLI behavior based on installation environment."""
    # Create a test script that tries to use the API Explorer
    tester.makepyfile(
        test_cli_api_explorer="""
        import subprocess
        import sys
        import importlib.util
        
        def test_api_explorer_command():
            # Check if we're in a visualization environment
            has_fastapi = importlib.util.find_spec("fastapi") is not None
            
            # Run the API Explorer command with --help to avoid actually launching it
            result = subprocess.run(
                [sys.executable, "-m", "pytest_insight", "api-explorer", "launch", "--help"],
                capture_output=True,
                text=True
            )
            
            combined_output = result.stdout + result.stderr
            
            if has_fastapi:
                # In visualization environment, command should succeed
                assert result.returncode == 0
                assert "Launch the pytest-insight API Explorer" in combined_output
            else:
                # In basic environment, should show helpful error about missing dependencies
                # The command might still return 0 with --help, so we check the output
                assert "Missing required dependencies" in combined_output or result.returncode != 0
                assert "pytest-insight[visualize]" in combined_output
    """
    )

    # Run the test
    result = tester.runpytest("-v", "test_cli_api_explorer.py")

    # Check that the test ran (it should pass in either environment)
    result.stdout.fnmatch_lines(["*test_api_explorer_command PASSED*"])
    assert result.ret == 0


def test_predictive_analytics_behavior(tester):
    """Test predictive analytics behavior based on installation environment."""
    # Create a test script that tries to use predictive analytics
    tester.makepyfile(
        test_predictive_env="""
        import importlib.util
        import pytest
        
        def test_predictive_analytics():
            # Check if we're in a visualization environment
            has_sklearn = importlib.util.find_spec("sklearn") is not None
            
            # Try to import and use predictive analytics
            try:
                from pytest_insight.core.core_api import get_predictive
                # Just create the instance, don't call any methods
                predictive = get_predictive()
                
                # Should only succeed if sklearn is available
                assert has_sklearn, "Predictive analytics worked without sklearn"
                
            except ImportError as e:
                # Should fail with helpful error if sklearn is not available
                if has_sklearn:
                    pytest.fail(f"Predictive analytics failed despite sklearn being available: {e}")
                else:
                    assert "pytest-insight[visualize]" in str(e)
    """
    )

    # Run the test
    result = tester.runpytest("-v", "test_predictive_env.py")

    # Check that the test ran (it should pass in either environment)
    result.stdout.fnmatch_lines(["*test_predictive_analytics PASSED*"])
    assert result.ret == 0
