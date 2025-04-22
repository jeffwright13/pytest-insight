"""Tests for the pytest-insight Web API endpoints.

This module contains tests for the FastAPI endpoints defined in web_api.py,
with a focus on ensuring that the endpoints correctly integrate with
the core pytest-insight components and handle various edge cases properly.
"""

import json
import os
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from pytest_insight.core.storage import ProfileManager, StorageProfile
from pytest_insight.rest_api.high_level_api import app

# Create a test client
client = TestClient(app)


class TestAPIEndpoints:
    """Tests for the FastAPI endpoints."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Create a mock profile manager
        self.mock_profile_manager = MagicMock(spec=ProfileManager)

        # Create mock profiles
        self.default_profile = StorageProfile(
            name="default", storage_type="json", file_path="/tmp/default.json"
        )

        self.test_profile = StorageProfile(
            name="test_profile", storage_type="json", file_path="/tmp/test_profile.json"
        )

        # Configure the mock profile manager
        self.mock_profile_manager.get_active_profile.return_value = self.default_profile
        self.mock_profile_manager.get_profile.return_value = self.test_profile
        self.mock_profile_manager.list_profiles.return_value = {
            "default": self.default_profile,
            "test_profile": self.test_profile,
        }

    @patch("pytest_insight.rest_api.high_level_api.get_profile_manager")
    def test_get_available_suts_active_profile(self, mock_get_profile_manager):
        """Test that get_available_suts returns SUTs from the active profile."""
        # Arrange
        mock_get_profile_manager.return_value = self.mock_profile_manager

        # Mock the InsightAPI.query().execute() call
        with patch(
            "pytest_insight.rest_api.high_level_api.InsightAPI"
        ) as mock_api_class:
            # The InsightAPI will be initialized with the active profile name
            mock_api = MagicMock()
            mock_api_class.return_value = mock_api

            mock_query = MagicMock()
            mock_api.query.return_value = mock_query

            mock_sessions = MagicMock()
            mock_sessions.sessions = [
                MagicMock(sut_name="sut1"),
                MagicMock(sut_name="sut2"),
                MagicMock(sut_name="sut1"),  # Duplicate to test deduplication
            ]
            mock_query.execute.return_value = mock_sessions

            # Act
            response = client.get("/api/suts")

            # Assert
            assert response.status_code == 200
            assert response.json() == {"suts": ["sut1", "sut2"], "count": 2}

            # Verify the correct methods were called
            mock_get_profile_manager.assert_called_once()
            self.mock_profile_manager.get_active_profile.assert_called_once()
            mock_api.query.assert_called_once()
            mock_query.execute.assert_called_once()

    @patch("pytest_insight.rest_api.high_level_api.get_profile_manager")
    def test_get_available_suts_all_profiles(self, mock_get_profile_manager):
        """Test that get_available_suts returns SUTs from all profiles when all_profiles=True."""
        # Arrange
        mock_get_profile_manager.return_value = self.mock_profile_manager

        # Mock the InsightAPI.with_profile().query().execute() calls
        with patch(
            "pytest_insight.rest_api.high_level_api.InsightAPI"
        ) as mock_api_class:
            # Setup for default profile
            mock_default_api = MagicMock()
            mock_api_class.return_value = mock_default_api

            mock_default_query = MagicMock()
            mock_default_api.query.return_value = mock_default_query

            mock_default_sessions = MagicMock()
            mock_default_sessions.sessions = [
                MagicMock(sut_name="sut1"),
                MagicMock(sut_name="sut2"),
            ]
            mock_default_query.execute.return_value = mock_default_sessions

            # Setup for test_profile
            mock_test_api = MagicMock()
            mock_default_api.with_profile.return_value = mock_test_api

            mock_test_query = MagicMock()
            mock_test_api.query.return_value = mock_test_query

            mock_test_sessions = MagicMock()
            mock_test_sessions.sessions = [
                MagicMock(sut_name="sut2"),
                MagicMock(sut_name="sut3"),
            ]
            mock_test_query.execute.return_value = mock_test_sessions

            # Act
            response = client.get("/api/suts?all_profiles=true")

            # Assert
            assert response.status_code == 200
            assert response.json() == {"suts": ["sut1", "sut2", "sut3"], "count": 3}

            # Verify the correct methods were called
            mock_get_profile_manager.assert_called_once()
            self.mock_profile_manager.get_active_profile.assert_called_once()
            self.mock_profile_manager.list_profiles.assert_called_once()
            mock_default_api.query.assert_called_once()
            mock_default_query.execute.assert_called_once()
            mock_default_api.with_profile.assert_called_with("test_profile")
            mock_test_api.query.assert_called_once()
            mock_test_query.execute.assert_called_once()

    @patch("pytest_insight.rest_api.high_level_api.get_profile_manager")
    def test_get_available_suts_api_error_fallback(self, mock_get_profile_manager):
        """Test that get_available_suts falls back to direct file access if API fails."""
        # Arrange
        mock_get_profile_manager.return_value = self.mock_profile_manager

        # Create a temporary test file
        test_file_path = "/tmp/default.json"

        # Update the default profile to point to our test file
        self.default_profile.file_path = test_file_path

        # Ensure get_profile returns our modified default profile
        self.mock_profile_manager.get_profile.return_value = self.default_profile

        # Mock the InsightAPI to raise an exception
        with patch(
            "pytest_insight.rest_api.high_level_api.InsightAPI"
        ) as mock_api_class:
            mock_api = MagicMock()
            mock_api_class.return_value = mock_api

            mock_query = MagicMock()
            mock_api.query.return_value = mock_query

            # Make the execute method raise an exception
            mock_query.execute.side_effect = Exception("API error")

            test_data = [
                {
                    "sut_name": "fallback_sut1",
                    "session_start_time": "2023-01-01T00:00:00",
                },
                {
                    "sut_name": "fallback_sut2",
                    "session_start_time": "2023-01-02T00:00:00",
                },
                {
                    "sut_name": "fallback_sut1",
                    "session_start_time": "2023-01-03T00:00:00",
                },  # Duplicate
            ]

            try:
                # Write test data to the file
                with open(test_file_path, "w") as f:
                    json.dump(test_data, f)

                # Act
                response = client.get("/api/suts")

                # Assert
                assert response.status_code == 200
                assert response.json() == {
                    "suts": ["fallback_sut1", "fallback_sut2"],
                    "count": 2,
                }

                # Verify the correct methods were called
                mock_get_profile_manager.assert_called_once()
                self.mock_profile_manager.get_active_profile.assert_called_once()
                self.mock_profile_manager.get_profile.assert_called_with(
                    self.default_profile.name
                )
                mock_api.query.assert_called_once()
                mock_query.execute.assert_called_once()

            finally:
                # Clean up the test file
                if os.path.exists(test_file_path):
                    os.remove(test_file_path)

    @patch("pytest_insight.rest_api.high_level_api.get_profile_manager")
    def test_get_available_suts_env_profile(self, mock_get_profile_manager):
        """Test that get_available_suts checks environment variable profile."""
        # Arrange
        mock_get_profile_manager.return_value = self.mock_profile_manager

        # Create a temporary test file for env profile
        env_file_path = "/tmp/env_profile.json"
        env_profile = StorageProfile(
            name="env_profile", storage_type="json", file_path=env_file_path
        )

        # Configure the mock profile manager to return the env_profile when requested
        self.mock_profile_manager.get_profile.side_effect = lambda name: (
            env_profile if name == "env_profile" else self.default_profile
        )

        # Mock the InsightAPI calls
        with (
            patch(
                "pytest_insight.rest_api.high_level_api.InsightAPI"
            ) as mock_api_class,
            patch.dict(os.environ, {"PYTEST_INSIGHT_PROFILE": "env_profile"}),
        ):
            # Setup for default profile API
            mock_default_api = MagicMock()

            # Setup for env profile API
            mock_env_api = MagicMock()

            # Configure the mock_api_class to return different instances for different calls
            mock_api_class.side_effect = [mock_default_api, mock_env_api]

            # Setup default profile query and results
            mock_default_query = MagicMock()
            mock_default_api.query.return_value = mock_default_query

            mock_default_sessions = MagicMock()
            mock_default_sessions.sessions = [MagicMock(sut_name="active_sut")]
            mock_default_query.execute.return_value = mock_default_sessions

            # Setup env profile query and results
            mock_env_query = MagicMock()
            mock_env_api.query.return_value = mock_env_query

            mock_env_sessions = MagicMock()
            mock_env_sessions.sessions = [
                MagicMock(sut_name="env_sut1"),
                MagicMock(sut_name="env_sut2"),
            ]
            mock_env_query.execute.return_value = mock_env_sessions

            # Write test data to the env profile file
            env_data = [
                {"sut_name": "env_sut1", "session_start_time": "2023-01-01T00:00:00"},
                {"sut_name": "env_sut2", "session_start_time": "2023-01-02T00:00:00"},
            ]

            try:
                # Write test data to the file
                with open(env_file_path, "w") as f:
                    json.dump(env_data, f)

                # Act
                response = client.get("/api/suts")

                # Assert
                assert response.status_code == 200
                result = response.json()
                assert "active_sut" in result["suts"]
                assert "env_sut1" in result["suts"]
                assert "env_sut2" in result["suts"]
                assert result["count"] == 3

                # Verify the correct methods were called
                mock_get_profile_manager.assert_called_once()
                self.mock_profile_manager.get_active_profile.assert_called_once()
                assert self.mock_profile_manager.get_profile.call_count >= 1

            finally:
                # Clean up the test file
                if os.path.exists(env_file_path):
                    os.remove(env_file_path)

    @patch("pytest_insight.rest_api.high_level_api.get_profile_manager")
    def test_get_available_suts_no_suts_found(self, mock_get_profile_manager):
        """Test that get_available_suts returns a default example when no SUTs are found."""
        # Arrange
        mock_get_profile_manager.return_value = self.mock_profile_manager

        # Mock the InsightAPI to return no SUTs
        with patch(
            "pytest_insight.rest_api.high_level_api.InsightAPI"
        ) as mock_api_class:
            # The InsightAPI will be initialized with the active profile name
            mock_api = MagicMock()
            mock_api_class.return_value = mock_api

            mock_query = MagicMock()
            mock_api.query.return_value = mock_query

            mock_sessions = MagicMock()
            mock_sessions.sessions = []  # No sessions
            mock_query.execute.return_value = mock_sessions

            # Act
            response = client.get("/api/suts")

            # Assert
            assert response.status_code == 200
            assert response.json() == {"suts": ["example-sut"], "count": 1}

            # Verify the correct methods were called
            mock_get_profile_manager.assert_called_once()
            self.mock_profile_manager.get_active_profile.assert_called_once()
            mock_api.query.assert_called_once()
            mock_query.execute.assert_called_once()
