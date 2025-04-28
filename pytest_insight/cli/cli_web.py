import logging
import os
import subprocess
from pathlib import Path

import psutil
import typer

# Add logging for diagnostics
logging.basicConfig(
    filename=os.path.expanduser("~/.pytest_insight/api_explorer_cli.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

app = typer.Typer(
    help="Web-based tools (API Explorer, Dashboard, etc.)",
    add_help_option=True,
    no_args_is_help=True,
)

api_explorer_app = typer.Typer(
    help="Self-discovering API Explorer UI (Swagger-like, chainable)",
    no_args_is_help=True,
)

PID_FILE = os.path.expanduser("~/.pytest_insight/api_explorer.pid")
INFO_FILE = os.path.expanduser("~/.pytest_insight/api_explorer.info")


@api_explorer_app.command("start", help="Start the API Explorer web UI (background by default)")
def start(
    host: str = typer.Option("127.0.0.1", help="Host to serve the API Explorer UI on"),
    port: int = typer.Option(8001, help="Port to serve the API Explorer UI on"),
    reload: bool = typer.Option(True, help="Enable auto-reload for development"),
    foreground: bool = typer.Option(False, "--foreground", help="Run in foreground (blocks terminal)"),
):
    """Start the API Explorer UI (FastAPI/Uvicorn)."""
    from importlib.util import find_spec

    logging.info(f"START called with host={host}, port={port}, reload={reload}, foreground={foreground}")
    if not find_spec("pytest_insight.web_api.explorer.explorer_app"):
        typer.echo("Explorer app not found. Please ensure it is installed.")
        logging.error("Explorer app not found.")
        raise typer.Exit(1)
    Path(os.path.dirname(PID_FILE)).mkdir(parents=True, exist_ok=True)
    if os.path.exists(PID_FILE):
        typer.echo(
            f"API Explorer appears to already be running (PID file exists at {PID_FILE}). Use 'insight web api-explorer stop' first."
        )
        logging.warning("PID file exists at start. Not starting new process.")
        raise typer.Exit(1)
    cmd = [
        "uvicorn",
        "pytest_insight.web_api.explorer.explorer_app:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        cmd.append("--reload")
    if foreground:
        typer.echo(f"Launching API Explorer UI at http://{host}:{port} (foreground, Ctrl+C to stop)...")
        logging.info(f"Running in foreground: {' '.join(cmd)}")
        subprocess.run(cmd)
    else:
        with open(os.devnull, "w") as devnull:
            proc = subprocess.Popen(cmd, stdout=devnull, stderr=devnull)
        with open(PID_FILE, "w") as f:
            f.write(str(proc.pid))
        with open(INFO_FILE, "w") as f:
            f.write(f"host={host}\nport={port}\npid={proc.pid}\ncmd={' '.join(cmd)}\n")
        logging.info(f"Started API Explorer at http://{host}:{port} (PID {proc.pid})")
        typer.echo(f"API Explorer started in background at http://{host}:{port} (PID {proc.pid})")
        typer.echo("To stop it, run: insight web api-explorer stop")


@api_explorer_app.command("stop", help="Stop the background API Explorer server")
def stop():
    """Stop the background API Explorer server."""
    logging.info("STOP called")
    if not os.path.exists(PID_FILE):
        typer.echo("No running API Explorer server found (no PID file).")
        if os.path.exists(INFO_FILE):
            os.remove(INFO_FILE)
        logging.warning("No PID file on stop. Nothing to stop.")
        raise typer.Exit(1)
    with open(PID_FILE) as f:
        pid = int(f.read().strip())
    try:
        p = psutil.Process(pid)
        children = p.children(recursive=True)
        for child in children:
            child.terminate()
        p.terminate()
        _, alive = psutil.wait_procs([p] + children, timeout=5)
        for a in alive:
            a.kill()
        typer.echo(f"Stopped API Explorer server and all child processes (PID {pid}).")
        logging.info(f"Stopped API Explorer server and children (PID {pid})")
    except psutil.NoSuchProcess:
        typer.echo(f"No process found with PID {pid}. Removing stale PID file.")
        logging.warning(f"No process with PID {pid} on stop.")
    except Exception as e:
        typer.echo(f"Error stopping server: {e}")
        logging.error(f"Error stopping server: {e}")
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    if os.path.exists(INFO_FILE):
        os.remove(INFO_FILE)


@api_explorer_app.command("status", help="Show status of the API Explorer server")
def status():
    """Show if the API Explorer server is running, with host/port info, PID, and stop/start commands."""
    logging.info("STATUS called")
    running = False
    host = port = pid = None
    orphaned = False
    orphaned_pids = []
    if os.path.exists(PID_FILE) and os.path.exists(INFO_FILE):
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            p = psutil.Process(pid)
            if p.is_running():
                running = True
        except Exception as e:
            running = False
            logging.warning(f"Exception in status: {e}")
            # Clean up stale info file if process is not running
            if os.path.exists(INFO_FILE):
                os.remove(INFO_FILE)
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        # Check for orphaned uvicorn/multiprocessing children
        for proc in psutil.process_iter(["pid", "cmdline"]):
            if proc.info["cmdline"] and any(
                "uvicorn" in arg or "multiprocessing" in arg for arg in proc.info["cmdline"]
            ):
                orphaned = True
                orphaned_pids.append(proc.info["pid"])
    if running:
        with open(INFO_FILE) as f:
            for line in f:
                if line.startswith("host="):
                    host = line.split("=", 1)[1].strip()
                elif line.startswith("port="):
                    port = line.split("=", 1)[1].strip()
                elif line.startswith("pid="):
                    pid = line.split("=", 1)[1].strip()
                elif line.startswith("cmd="):
                    line.split("=", 1)[1].strip()
        typer.echo("API Explorer server is running")
        typer.echo(f"URL: http://{host}:{port}")
        typer.echo(f"PID: {pid}")
        typer.echo("To stop: insight web api-explorer stop")
        logging.info(f"STATUS: running at http://{host}:{port} (PID {pid})")
    else:
        typer.echo("API Explorer server is not running")
        typer.echo("To start: insight web api-explorer start")
        if orphaned:
            typer.echo(
                f"Orphaned: Warning: Orphaned uvicorn/multiprocessing process(es) detected: {orphaned_pids}. You may need to kill them manually."
            )
            logging.warning(f"Orphaned processes detected: {orphaned_pids}")


app.add_typer(api_explorer_app, name="api-explorer")
