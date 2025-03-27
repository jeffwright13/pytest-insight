#!/usr/bin/env python3
"""
Quick and dirty metrics server for pytest-insight.

This script runs a FastAPI server that exposes pytest-insight metrics
in a format suitable for Grafana visualization.
"""

import argparse
import os
import webbrowser
from pathlib import Path

import uvicorn


def start_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = True) -> None:
    """Start the FastAPI metrics server."""
    print(f"Starting pytest-insight metrics server at http://{host}:{port}")
    print("\nAvailable endpoints:")
    print(f"  Health check: http://{host}:{port}/health")
    print(f"  Metrics search: http://{host}:{port}/search")
    print(f"  Metrics query: http://{host}:{port}/query")

    # Set environment variables if needed
    db_path = os.environ.get("PYTEST_INSIGHT_DB_PATH")
    if db_path:
        print(f"Using database at: {db_path}")
    else:
        print("Using default database location")

    # Run the server - pointing to the correct module
    uvicorn.run("pytest_insight.api:app", host=host, port=port, reload=reload)


def open_grafana_dashboard(host: str = "127.0.0.1", port: int = 3000) -> None:
    """Open the Grafana dashboard in a web browser."""
    url = f"http://{host}:{port}"
    print(f"Opening Grafana dashboard at {url}")
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="Run pytest-insight metrics server for Grafana")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload on code changes")
    parser.add_argument("--db-path", type=str, help="Path to the test sessions database file")
    parser.add_argument("--open-grafana", action="store_true", help="Open Grafana dashboard in browser")
    parser.add_argument("--grafana-port", type=int, default=3000, help="Grafana port (if using --open-grafana)")

    args = parser.parse_args()

    # Set database path as environment variable if specified
    if args.db_path:
        db_path = Path(args.db_path).expanduser().resolve()
        print(f"Using custom database: {db_path}")
        os.environ["PYTEST_INSIGHT_DB_PATH"] = str(db_path)

    # Open Grafana if requested
    if args.open_grafana:
        open_grafana_dashboard(host=args.host, port=args.grafana_port)

    # Start the server
    start_server(host=args.host, port=args.port, reload=not args.no_reload)


if __name__ == "__main__":
    main()
