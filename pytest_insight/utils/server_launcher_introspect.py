#!/usr/bin/env python3
"""Simple launcher for the pytest-insight web interface."""

import argparse
import json
import os
from pathlib import Path

import uvicorn


def main():
    """Launch the pytest-insight web interface."""
    parser = argparse.ArgumentParser(description="Run pytest-insight API server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on code changes")
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to the test sessions database file",
    )

    args = parser.parse_args()

    # Set database path as environment variable if specified
    if args.db_path:
        # Convert to absolute path and resolve any symlinks
        db_path = Path(args.db_path).expanduser().resolve()
        print(f"Using custom database: {db_path}")

        # Create an empty file if it doesn't exist
        if not db_path.exists():
            print(f"Creating new database file: {db_path}")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with open(db_path, "w") as f:
                f.write("[]")

        # Set environment variable
        os.environ["PYTEST_INSIGHT_DB_PATH"] = str(db_path)
    else:
        print("Using default database location")

    print(f"Starting pytest-insight API server at http://{args.host}:{args.port}")
    print("\nAvailable interfaces:")
    print(f"  Main dashboard: http://{args.host}:{args.port}/")
    print(f"  Test data generator: http://{args.host}:{args.port}/generator")
    print(f"  Test selector: http://{args.host}:{args.port}/selector")
    print(f"  API documentation: http://{args.host}:{args.port}/docs")

    # Create config.json for uvicorn reload to pick up
    if args.reload:
        config = {"db_path": os.environ.get("PYTEST_INSIGHT_DB_PATH", "")}
        # Adjust the path to be relative to the package
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, "w") as f:
            json.dump(config, f)
        print(f"Created config at {config_path}")

    # Updated import path to reflect the new folder structure
    uvicorn.run("pytest_insight.rest_api.high_level_api_introspect:introspected_app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
