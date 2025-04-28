import os
import shutil
from datetime import datetime

import typer
from quantiphy import Quantity
from rich import box
from rich.console import Console
from rich.table import Table

from pytest_insight.core.storage import get_profile_manager, get_profile_metadata
from pytest_insight.utils.utils import NormalizedDatetime

app = typer.Typer(help="Manage storage profiles", no_args_is_help=True)
console = Console()


def mid_truncate(text, max_length=32, ellipsis="..."):
    """Truncate long strings in the middle, preserving start and end."""
    if not text or len(text) <= max_length:
        return text
    keep = max_length - len(ellipsis)
    left = keep // 2
    right = keep - left
    return f"{text[:left]}{ellipsis}{text[-right:]}"


@app.command()
def create(
    name: str,
    type: str = typer.Option(..., help="Type of storage (e.g., sqlite, json)"),
    path: str = typer.Option(None, help="Storage path or URI"),
):
    """Create a new storage profile."""
    pm = get_profile_manager()
    try:
        profile = pm.create_profile(name, type, path)
        typer.echo(f"[profile] Created profile '{name}' of type '{type}' at '{profile.file_path}'")
    except Exception as e:
        typer.secho(f"[profile] Error creating profile: {e}", fg=typer.colors.RED)


@app.command()
def list(show_all: bool = typer.Option(False, "--show-all", help="Show all profile metadata (created/modified/by)")):
    """List all available storage profiles."""
    pm = get_profile_manager()
    active = pm.active_profile_name
    meta = get_profile_metadata()
    profiles = None
    if isinstance(meta, dict):
        if "profiles" in meta:
            profiles = meta["profiles"]
        else:
            if all(isinstance(v, dict) for v in meta.values()):
                profiles = meta
    if not profiles:
        typer.echo("[profile] No profiles found.")
        return
    term_width = shutil.get_terminal_size((120, 20)).columns
    min_other = 2 + 18 + 8 + 10 + 8 + 8  # mark, name, type, path, size, padding
    path_col_width = max(10, term_width - min_other)
    table = Table(title="Pytest-Insight Storage Profiles", box=box.ROUNDED, show_lines=False)
    table.add_column("Active", style="bold green", no_wrap=True)
    table.add_column("Name", style="bold", no_wrap=True)
    table.add_column("Type", style="cyan", no_wrap=True)
    table.add_column("Path", style="magenta", no_wrap=False, width=path_col_width)
    table.add_column("Size", style="yellow", justify="right", no_wrap=True)
    if show_all:
        table.add_column("Created", style="dim", no_wrap=True)
        table.add_column("Created By", style="dim", no_wrap=True)
        table.add_column("Modified", style="dim", no_wrap=True)
        table.add_column("Modified By", style="dim", no_wrap=True)
    for name, info in profiles.items():
        is_active = name == active
        mark = "*" if is_active else ""
        file_path = info.get("file_path")
        storage_type = str(info.get("storage_type", "?"))
        size = "-"
        shown_path = "-"
        if storage_type in {"json", "sqlite"}:
            if not file_path:
                ext = ".json" if storage_type == "json" else ".sqlite"
                candidate = os.path.expanduser(f"~/.pytest_insight/profiles/{name}{ext}")
                if os.path.isfile(candidate):
                    file_path = candidate
            if file_path and os.path.isfile(file_path):
                shown_path = mid_truncate(str(file_path), path_col_width)
                try:
                    size_bytes = os.path.getsize(file_path)
                    size = Quantity(size_bytes, "B").render(prec=2, strip_zeros=False)
                except Exception:
                    size = "?"
            else:
                shown_path = "-"
        else:
            shown_path = file_path or "-"
        row = [mark, name, storage_type, shown_path, size]
        if show_all:
            created = info.get("created")
            created_by = info.get("created_by", "-")
            if created:
                if isinstance(created, datetime):
                    created_fmt = created.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    created_fmt = str(NormalizedDatetime(created))[:19]
            else:
                created_fmt = "-"
            modified = info.get("last_modified")
            modified_by = info.get("last_modified_by", "-")
            if modified:
                if isinstance(modified, datetime):
                    modified_fmt = modified.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    modified_fmt = str(NormalizedDatetime(modified))[:19]
            else:
                modified_fmt = "-"
            row.extend([created_fmt, created_by, modified_fmt, modified_by])
        table.add_row(*row)
    console.print(table)


@app.command()
def delete(name: str):
    """Delete a storage profile."""
    pm = get_profile_manager()
    try:
        pm.delete_profile(name)
        typer.echo(f"[profile] Deleted profile '{name}'")
    except Exception as e:
        typer.secho(f"[profile] Error deleting profile: {e}", fg=typer.colors.RED)


@app.command()
def set(name: str):
    """Set the active/default storage profile."""
    pm = get_profile_manager()
    try:
        pm.switch_profile(name)
        typer.echo(f"[profile] Set profile '{name}' as active/default")
    except Exception as e:
        typer.secho(f"[profile] Error setting active profile: {e}", fg=typer.colors.RED)
