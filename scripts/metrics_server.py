#!/usr/bin/env python3
"""Standalone script to manage the pytest-insight metrics server."""

import argparse
import uvicorn
import requests
from pathlib import Path

def start_server(port: int = 8000, reload: bool = True) -> None:
    """Start the FastAPI metrics server."""
    print(f"Starting metrics server on port {port}")
    uvicorn.run("pytest_insight.server:app", port=port, reload=reload)

def check_status(port: int = 8000) -> None:
    """Check if server is running and responding."""
    try:
        response = requests.get(f"http://localhost:{port}/health")
        if response.status_code == 200:
            print("✓ Server is running")
            print("\nAvailable endpoints:")
            print(f"  Health check: http://localhost:{port}/health")
            print(f"  Metrics search: http://localhost:{port}/search")
            print(f"  Metrics query: http://localhost:{port}/query")
        else:
            print("✗ Server is not responding correctly")
    except requests.ConnectionError:
        print("✗ Server is not running")

def main():
    parser = argparse.ArgumentParser(description="Manage pytest-insight metrics server")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start metrics server")
    start_parser.add_argument("--port", "-p", type=int, default=8000, help="Port number")
    start_parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")

    # Status command
    status_parser = subparsers.add_parser("status", help="Check server status")
    status_parser.add_argument("--port", "-p", type=int, default=8000, help="Port number")

    args = parser.parse_args()

    if args.command == "start":
        start_server(args.port, not args.no_reload)
    elif args.command == "status":
        check_status(args.port)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
