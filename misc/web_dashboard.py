#!/usr/bin/env python3
"""
pytest-insight Web Dashboard

A quick and dirty web interface for interacting with pytest-insight's API.
"""

import os

from flask import Flask, jsonify, render_template, request
from pytest_insight.core.core_api import create_profile, delete_profile, get_storage_instance, list_profiles
from pytest_insight.core.insights import Insights
from pytest_insight.core.query import Query
from pytest_insight.utils.analyze_test_data import generate_sample_data

app = Flask(__name__)
app.config["SECRET_KEY"] = "pytest-insight-dashboard"
app.config["JSON_SORT_KEYS"] = False
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Global variables to store state
current_profile = None
current_insights = None
current_query = None


@app.route("/")
def index():
    """Main dashboard page."""
    profiles = list_profiles()
    return render_template("index.html", profiles=profiles, current_profile=current_profile)


@app.route("/profiles", methods=["GET", "POST"])
def profiles():
    """Manage profiles."""
    global current_profile, current_insights, current_query

    if request.method == "POST":
        action = request.form.get("action")

        if action == "create":
            profile_name = request.form.get("profile_name")
            storage_type = request.form.get("storage_type")
            storage_path = request.form.get("storage_path")

            try:
                create_profile(profile_name, storage_type, storage_path)
                return jsonify({"status": "success", "message": f"Profile {profile_name} created successfully"})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)})

        elif action == "delete":
            profile_name = request.form.get("profile_name")

            try:
                delete_profile(profile_name)
                if current_profile == profile_name:
                    current_profile = None
                    current_insights = None
                    current_query = None
                return jsonify({"status": "success", "message": f"Profile {profile_name} deleted successfully"})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)})

        elif action == "select":
            profile_name = request.form.get("profile_name")

            try:
                # Test if profile exists and can be loaded
                storage = get_storage_instance(profile_name)
                sessions = storage.load_sessions()

                current_profile = profile_name
                current_insights = Insights(profile_name=profile_name)
                current_query = Query(profile_name=profile_name)

                return jsonify(
                    {
                        "status": "success",
                        "message": f"Profile {profile_name} selected successfully",
                        "session_count": len(sessions) if sessions else 0,
                    }
                )
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)})

        elif action == "generate_sample":
            try:
                generate_sample_data()
                return jsonify({"status": "success", "message": "Sample data generated successfully"})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)})

    # GET request
    profiles = list_profiles()
    return jsonify({"profiles": profiles})


@app.route("/query", methods=["GET", "POST"])
def query():
    """Execute queries."""
    global current_query

    if not current_profile:
        return jsonify({"status": "error", "message": "No profile selected"})

    if request.method == "POST":
        action = request.form.get("action")

        if action == "reset":
            current_query = Query(profile_name=current_profile)
            return jsonify({"status": "success", "message": "Query reset successfully"})

        elif action == "filter_session":
            filter_type = request.form.get("filter_type")
            filter_value = request.form.get("filter_value")

            try:
                if filter_type == "days":
                    current_query.filter_by_days(int(filter_value))
                elif filter_type == "sut":
                    current_query.filter_by_sut(filter_value)
                elif filter_type == "version":
                    current_query.filter_by_version(filter_value)
                elif filter_type == "session_id":
                    current_query.filter_by_session_id(filter_value)

                return jsonify(
                    {
                        "status": "success",
                        "message": f"Applied {filter_type} filter with value {filter_value}",
                        "session_count": len(current_query.get_sessions()),
                    }
                )
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)})

        elif action == "filter_test":
            filter_type = request.form.get("filter_type")
            filter_value = request.form.get("filter_value")

            try:
                if filter_type == "name":
                    current_query.filter_by_test_name(filter_value)
                elif filter_type == "outcome":
                    current_query.filter_by_outcome(filter_value)
                elif filter_type == "duration":
                    min_val = float(request.form.get("min_value", 0))
                    max_val = float(request.form.get("max_value", 0))
                    current_query.filter_by_duration(min_val, max_val)

                return jsonify(
                    {
                        "status": "success",
                        "message": f"Applied test {filter_type} filter with value {filter_value}",
                        "test_count": len(current_query.get_test_results()),
                    }
                )
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)})

    # GET request - return current query info
    if current_query:
        try:
            return jsonify(
                {
                    "session_count": len(current_query.get_sessions()),
                    "test_count": len(current_query.get_test_results()),
                }
            )
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    else:
        return jsonify({"status": "error", "message": "No query initialized"})


@app.route("/insights", methods=["GET", "POST"])
def insights():
    """Get insights from the data."""
    global current_insights

    if not current_profile:
        return jsonify({"status": "error", "message": "No profile selected"})

    if request.method == "POST":
        action = request.form.get("action")

        if not current_insights:
            current_insights = Insights(profile_name=current_profile)

        try:
            result = None

            # Session insights
            if action == "session_metrics":
                result = current_insights.sessions.session_metrics()
            elif action == "session_summary":
                result = current_insights.sessions.session_summary()

            # Test insights
            elif action == "test_metrics":
                result = current_insights.tests.test_metrics()
            elif action == "test_summary":
                result = current_insights.tests.test_summary()
            elif action == "flaky_tests":
                result = current_insights.tests.flaky_tests()
            elif action == "slowest_tests":
                limit = int(request.form.get("limit", 10))
                result = current_insights.tests.slowest_tests(limit=limit)
            elif action == "test_health_score":
                result = current_insights.tests.test_health_score()
            elif action == "error_patterns":
                result = current_insights.tests.error_patterns()
            elif action == "dependency_graph":
                result = current_insights.tests.dependency_graph()

            # Trend insights
            elif action == "duration_trends":
                result = current_insights.trends.duration_trends()
            elif action == "outcome_trends":
                result = current_insights.trends.outcome_trends()

            # Comparison insights
            elif action == "compare_sessions":
                session_id1 = request.form.get("session_id1")
                session_id2 = request.form.get("session_id2")
                result = current_insights.compare.sessions(session_id1, session_id2)
            elif action == "compare_versions":
                version1 = request.form.get("version1")
                version2 = request.form.get("version2")
                result = current_insights.compare.versions(version1, version2)

            if result:
                return jsonify({"status": "success", "result": result})
            else:
                return jsonify({"status": "error", "message": f"No result for action {action}"})

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})

    # GET request
    return jsonify({"status": "success", "message": "Insights API ready"})


@app.route("/raw_data", methods=["GET"])
def raw_data():
    """Get raw data from the current profile."""
    if not current_profile:
        return jsonify({"status": "error", "message": "No profile selected"})

    data_type = request.args.get("type", "sessions")

    try:
        if data_type == "sessions":
            storage = get_storage_instance(current_profile)
            sessions = storage.load_sessions()

            # Convert to serializable format
            session_data = []
            for session in sessions:
                session_data.append(
                    {
                        "session_id": session.session_id,
                        "timestamp": str(session.timestamp),
                        "sut": session.sut,
                        "version": session.version,
                        "platform": session.platform,
                        "test_count": len(session.test_results),
                    }
                )

            return jsonify({"sessions": session_data})

        elif data_type == "tests" and current_query:
            tests = current_query.get_test_results()

            # Convert to serializable format
            test_data = []
            for test in tests:
                test_data.append(
                    {
                        "nodeid": test.nodeid,
                        "outcome": test.outcome.to_str(),
                        "duration": test.duration,
                        "session_id": test.session_id,
                    }
                )

            return jsonify({"tests": test_data})

        else:
            return jsonify({"status": "error", "message": f"Invalid data type: {data_type}"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


if __name__ == "__main__":
    # Create templates directory if it doesn't exist
    os.makedirs("templates", exist_ok=True)
    app.run(debug=True, port=5000)
