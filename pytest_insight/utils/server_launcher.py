#!/usr/bin/env python3
"""Launcher for the pytest-insight web interfaces."""

import argparse
import json
import multiprocessing
import os
from pathlib import Path

import uvicorn


def run_high_level_api(host, port, reload):
    """Run the high-level API server."""
    print(f"Starting pytest-insight High-Level API server at http://{host}:{port}")
    print("\nAvailable interfaces:")
    print(f"  Main dashboard: http://{host}:{port}/")
    print(f"  Test data generator: http://{host}:{port}/generator")
    print(f"  Test selector: http://{host}:{port}/selector")
    print(f"  API documentation: http://{host}:{port}/docs")

    uvicorn.run(
        "pytest_insight.rest_api.high_level_api:app",
        host=host,
        port=port,
        reload=reload,
    )


def run_introspected_api(host, port, reload):
    """Run the introspected API server."""
    print(f"Starting pytest-insight Introspected API server at http://{host}:{port}")
    print("\nAvailable interfaces:")
    print(f"  Introspected API dashboard: http://{host}:{port}/")
    print(f"  API documentation: http://{host}:{port}/docs")

    uvicorn.run(
        "pytest_insight.rest_api.introspective_api:introspected_app",
        host=host,
        port=port,
        reload=reload,
    )


def main():
    """Launch the pytest-insight web interfaces."""
    parser = argparse.ArgumentParser(description="Run pytest-insight API servers")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind the servers to"
    )
    parser.add_argument(
        "--high-level-port",
        type=int,
        default=8000,
        help="Port for the high-level API server",
    )
    parser.add_argument(
        "--introspected-port",
        type=int,
        default=8001,
        help="Port for the introspected API server",
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload on code changes"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to the test sessions database file",
    )
    parser.add_argument(
        "--high-level-only",
        action="store_true",
        help="Run only the high-level API server",
    )
    parser.add_argument(
        "--introspected-only",
        action="store_true",
        help="Run only the introspected API server",
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

    # Create config.json for uvicorn reload to pick up
    if args.reload:
        config = {"db_path": os.environ.get("PYTEST_INSIGHT_DB_PATH", "")}
        # Adjust the path to be relative to the package
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, "w") as f:
            json.dump(config, f)
        print(f"Created config at {config_path}")

    # Determine which servers to run
    run_high_level = not args.introspected_only
    run_introspected = not args.high_level_only

    if not run_high_level and not run_introspected:
        print("Error: You've disabled both API servers. Please enable at least one.")
        return

    # Print overall information
    print("\n=== pytest-insight API Servers ===")
    if run_high_level and run_introspected:
        print(f"Running both API servers:")
        print(f"  High-Level API: http://{args.host}:{args.high_level_port}")
        print(f"  Introspected API: http://{args.host}:{args.introspected_port}")
    elif run_high_level:
        print(f"Running High-Level API only: http://{args.host}:{args.high_level_port}")
    else:
        print(
            f"Running Introspected API only: http://{args.host}:{args.introspected_port}"
        )
    print("================================\n")

    # Start the servers in separate processes
    processes = []

    if run_high_level:
        high_level_process = multiprocessing.Process(
            target=run_high_level_api,
            args=(args.host, args.high_level_port, args.reload),
        )
        high_level_process.start()
        processes.append(high_level_process)

    if run_introspected:
        introspected_process = multiprocessing.Process(
            target=run_introspected_api,
            args=(args.host, args.introspected_port, args.reload),
        )
        introspected_process.start()
        processes.append(introspected_process)

    # Wait for all processes to complete
    for process in processes:
        process.join()


if __name__ == "__main__":
    main()
