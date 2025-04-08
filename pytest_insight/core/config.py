"""
Configuration module for pytest-insight.

This module handles loading and managing configurations from different sources:
- Default configurations built into the code
- Project-level configuration file (pytest-insight.toml or pyproject.toml section)
- Environment variables for CI environments
- Command-line arguments for one-off overrides
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import tomli

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "reports": {
        "summary": {
            "enabled": True,
            "metrics": ["pass_rate", "flaky_rate", "test_count", "session_count"],
            "sections": ["top_failures", "top_flaky", "performance_issues"]
        },
        "stability": {
            "enabled": True,
            "threshold": 0.85,  # Minimum pass rate to be considered stable
            "flaky_threshold": 0.05  # Maximum flaky rate to be considered stable
        },
        "performance": {
            "enabled": True,
            "slow_test_threshold": 1.0  # Tests taking longer than 1s are considered slow
        },
        "patterns": {
            "enabled": True,
            "min_frequency": 2  # Minimum occurrences to identify a pattern
        },
        "trends": {
            "enabled": True,
            "window_size": 7  # Days to include in each trend point
        },
        "dependencies": {
            "enabled": True,
            "min_correlation": 0.5  # Minimum correlation to consider a dependency
        }
    }
}


def find_project_config() -> Optional[Dict[str, Any]]:
    """
    Look for a pytest-insight configuration in the project.
    
    Searches for:
    1. pytest-insight.toml in the current directory
    2. pytest-insight section in pyproject.toml
    
    Returns:
        Dict or None: Configuration dictionary if found, None otherwise
    """
    # Look for dedicated config file
    config_path = Path.cwd() / "pytest-insight.toml"
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                return tomli.load(f)
        except Exception as e:
            logger.warning(f"Error loading {config_path}: {e}")
    
    # Look for section in pyproject.toml
    pyproject_path = Path.cwd() / "pyproject.toml"
    if pyproject_path.exists():
        try:
            with open(pyproject_path, "rb") as f:
                pyproject = tomli.load(f)
                if "tool" in pyproject and "pytest-insight" in pyproject["tool"]:
                    return pyproject["tool"]["pytest-insight"]
        except Exception as e:
            logger.warning(f"Error loading pytest-insight section from {pyproject_path}: {e}")
    
    return None


def parse_value(value: str) -> Any:
    """
    Parse a string value into the appropriate Python type.
    
    Handles:
    - Booleans ("true", "false")
    - Numbers (integers, floats)
    - Lists (comma-separated values)
    - JSON objects
    - Plain strings
    
    Args:
        value: String value to parse
        
    Returns:
        Parsed value in the appropriate type
    """
    # Handle boolean values
    true_values = {"true", "yes", "1"}
    false_values = {"false", "no", "0"}
    
    value_lower = value.lower()
    if value_lower in true_values:
        return True
    if value_lower in false_values:
        return False
    
    # Handle numeric values
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        pass
    
    # Handle lists (comma-separated values)
    if "," in value:
        return [parse_value(item.strip()) for item in value.split(",")]
    
    # Handle JSON
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        # Default to string if not JSON
        return value


def load_from_env() -> Dict[str, Any]:
    """
    Load configuration from environment variables.
    
    Environment variables should be prefixed with PYTEST_INSIGHT_
    Example: PYTEST_INSIGHT_REPORTS_SUMMARY_ENABLED=true
    
    Returns:
        Dict: Configuration dictionary from environment variables
    """
    config = {}
    
    # Parse environment variables with a prefix
    prefix = "PYTEST_INSIGHT_"
    for key, value in os.environ.items():
        if key.startswith(prefix):
            # Convert PYTEST_INSIGHT_REPORTS_SUMMARY_ENABLED to reports.summary.enabled
            config_key = key[len(prefix):].lower().replace("_", ".")
            # Parse the value
            config[config_key] = parse_value(value)
    
    return config


def nested_update(target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a nested dictionary with values from another nested dictionary.
    
    Args:
        target: Target dictionary to update
        source: Source dictionary with new values
        
    Returns:
        Updated target dictionary
    """
    for key, value in source.items():
        if isinstance(value, dict) and key in target and isinstance(target[key], dict):
            # Recursively update nested dictionaries
            nested_update(target[key], value)
        else:
            # Update or add the value
            target[key] = value
    return target


def load_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from all sources, with the following precedence:
    1. Command-line specified config file (highest)
    2. Environment variables
    3. Project configuration file
    4. Default configuration (lowest)
    
    Args:
        config_file: Optional path to a specific configuration file
        
    Returns:
        Dict: Merged configuration dictionary
    """
    # Start with defaults
    config = DEFAULT_CONFIG.copy()
    
    # Look for project config file
    project_config = find_project_config()
    if project_config:
        config = nested_update(config, project_config)
    
    # Apply environment variables
    env_config = load_from_env()
    if env_config:
        # Convert flat env config to nested structure
        nested_env_config = {}
        for key, value in env_config.items():
            parts = key.split(".")
            current = nested_env_config
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value
        
        config = nested_update(config, nested_env_config)
    
    # Load specific config file if provided
    if config_file:
        try:
            with open(config_file, "rb") as f:
                file_config = tomli.load(f)
                config = nested_update(config, file_config)
        except Exception as e:
            logger.warning(f"Error loading config file {config_file}: {e}")
    
    return config


class InsightConfig:
    """
    Configuration manager for pytest-insight.
    
    Provides access to configuration values with support for overrides.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config: Optional initial configuration dictionary
        """
        self._config = config or load_config()
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Get a configuration value by path.
        
        Args:
            path: Dot-separated path to the configuration value
            default: Default value to return if the path is not found
            
        Returns:
            Configuration value or default
        """
        parts = path.split(".")
        current = self._config
        
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        
        return current
    
    def set(self, path: str, value: Any) -> None:
        """
        Set a configuration value by path.
        
        Args:
            path: Dot-separated path to the configuration value
            value: Value to set
        """
        parts = path.split(".")
        current = self._config
        
        # Navigate to the parent of the target key
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Set the value
        current[parts[-1]] = value
    
    def update(self, config: Dict[str, Any]) -> None:
        """
        Update the configuration with a new dictionary.
        
        Args:
            config: New configuration values
        """
        self._config = nested_update(self._config, config)
    
    def as_dict(self) -> Dict[str, Any]:
        """
        Get the complete configuration as a dictionary.
        
        Returns:
            Dict: Complete configuration
        """
        return self._config.copy()
    
    def is_enabled(self, report_type: str) -> bool:
        """
        Check if a specific report type is enabled.
        
        Args:
            report_type: Type of report to check
            
        Returns:
            bool: True if enabled, False otherwise
        """
        return self.get(f"reports.{report_type}.enabled", False)
    
    def get_metrics(self, report_type: str = "summary") -> List[str]:
        """
        Get the list of metrics to include in a report.
        
        Args:
            report_type: Type of report
            
        Returns:
            List[str]: List of metric names
        """
        return self.get(f"reports.{report_type}.metrics", [])
    
    def get_sections(self, report_type: str = "summary") -> List[str]:
        """
        Get the list of sections to include in a report.
        
        Args:
            report_type: Type of report
            
        Returns:
            List[str]: List of section names
        """
        return self.get(f"reports.{report_type}.sections", [])


# Global configuration instance
config = InsightConfig()


def get_config() -> InsightConfig:
    """
    Get the global configuration instance.
    
    Returns:
        InsightConfig: Global configuration instance
    """
    return config


def configure(new_config: Dict[str, Any]) -> None:
    """
    Update the global configuration.
    
    Args:
        new_config: New configuration values
    """
    global config
    config.update(new_config)
