"""Main CLI functionality for pytest-insight."""

import json
import traceback
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from pytest_insight.core.storage import (
    create_profile,
    get_active_profile,
    get_profile_manager,
    get_profile_metadata,
    list_profiles,
    load_sessions,
    switch_profile,
)
from pytest_insight.utils.db_generator import PracticeDataGenerator

# Create CLI apps
app = typer.Typer(
    help="Command-line interface for pytest-insight",
    context_settings={"help_option_names": ["--help", "-h"]},
)

profile_app = typer.Typer(
    help="Manage storage profiles",
    context_settings={"help_option_names": ["--help", "-h"]},
)

generate_app = typer.Typer(
    help="Generate practice test data",
    context_settings={"help_option_names": ["--help", "-h"]},
)

# Add subcommands to main app
app.add_typer(profile_app, name="profile")
app.add_typer(generate_app, name="generate")


# Profile management commands
@profile_app.command("list")
def list_all_profiles():
    """List all available storage profiles."""
    console = Console()
    profiles = list_profiles()
    active_profile = get_active_profile()

    table = Table(title="Storage Profiles")
    table.add_column("Profile Name")
    table.add_column("Path")
    table.add_column("Active")

    for profile in profiles:
        is_active = "✓" if profile.name == active_profile.name else ""
        table.add_row(profile.name, profile.path, is_active)

    console.print(table)


@profile_app.command("create")
def create_new_profile(
    name: str = typer.Argument(..., help="Name of the profile to create"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Path to store the profile data"),
):
    """Create a new storage profile."""
    console = Console()
    try:
        profile = create_profile(name, path)
        console.print(f"Created profile [bold]{profile.name}[/bold] at {profile.path}")
    except Exception as e:
        console.print(f"Error creating profile: {str(e)}", style="red")


@profile_app.command("switch")
def switch_to_profile(name: str = typer.Argument(..., help="Name of the profile to switch to")):
    """Switch to a different storage profile."""
    console = Console()
    try:
        profile = switch_profile(name)
        console.print(f"Switched to profile [bold]{profile.name}[/bold]")
    except Exception as e:
        console.print(f"Error switching profile: {str(e)}", style="red")


@profile_app.command("active")
def show_active_profile():
    """Show the active storage profile."""
    console = Console()
    profile = get_active_profile()
    console.print(f"Active profile: [bold]{profile.name}[/bold] at {profile.path}")


@profile_app.command("load")
def load_profile_sessions(path: str = typer.Argument(..., help="Path to the sessions file")):
    """Load sessions from a file into the active profile."""
    console = Console()
    try:
        count = load_sessions(path)
        console.print(f"Loaded {count} sessions into the active profile")
    except Exception as e:
        console.print(f"Error loading sessions: {str(e)}", style="red")


@profile_app.command("metadata")
def show_profile_metadata(
    profile_name: Optional[str] = typer.Argument(
        None, help="Name of the profile to show metadata for. If not provided, shows metadata for all profiles."
    ),
):
    """Show metadata about storage profiles, including creation and modification timestamps."""
    console = Console()
    metadata = get_profile_metadata(profile_name)

    if "error" in metadata:
        console.print(f"[bold red]Error:[/bold red] {metadata['error']}")
        return

    # Show global metadata
    console.print("[bold blue]Profiles Configuration[/bold blue]")
    console.print(f"Last modified: {metadata['last_modified']}")
    console.print(f"Modified by: {metadata['modified_by']}")
    console.print(f"Active profile: {metadata['active_profile']}")
    console.print(f"Total profiles: {metadata['profiles_count']}")
    console.print()

    # Show specific profile if requested
    if profile_name and "profile" in metadata:
        profile = metadata["profile"]
        console.print(f"[bold green]Profile: {profile['name']}[/bold green]")
        console.print(f"Storage type: {profile['storage_type']}")
        console.print(f"File path: {profile['file_path']}")

        # Format timestamps for display
        created = profile["created"].isoformat() if hasattr(profile["created"], "isoformat") else profile["created"]
        created_by = profile["created_by"]
        modified_at = (
            profile["last_modified"].isoformat()
            if hasattr(profile["last_modified"], "isoformat")
            else profile["last_modified"]
        )
        modified_by = profile["last_modified_by"]

        console.print(f"Created at: {created}")
        console.print(f"Created by: {created_by}")
        console.print(f"Last modified at: {modified_at}")
        console.print(f"Last modified by: {modified_by}")
    # Show all profiles
    elif "profiles" in metadata:
        table = Table(title="Profile Timestamps")
        table.add_column("Profile Name")
        table.add_column("Storage Type")
        table.add_column("Created By")
        table.add_column("Created At")
        table.add_column("Modified By")
        table.add_column("Modified At")

        for name, profile in metadata["profiles"].items():
            # Format timestamps for display
            created = profile["created"].isoformat() if hasattr(profile["created"], "isoformat") else profile["created"]
            modified_at = (
                profile["last_modified"].isoformat()
                if hasattr(profile["last_modified"], "isoformat")
                else profile["last_modified"]
            )

            table.add_row(
                name, profile["storage_type"], profile["created_by"], created, profile["last_modified_by"], modified_at
            )

        console.print(table)


# Data generation commands
@generate_app.command("practice")
def generate_practice_data(
    num_test_runs: int = typer.Option(3, "--runs", "-r", help="Number of test runs to generate"),
    num_tests_per_run: int = typer.Option(20, "--tests", "-t", help="Number of tests per run"),
    num_sessions_per_run: int = typer.Option(3, "--sessions", "-s", help="Number of sessions per run"),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Output file for generated data"),
    load_to_profile: bool = typer.Option(False, "--load", "-l", help="Load generated data to active profile"),
):
    """Generate practice test data."""
    console = Console()
    try:
        generator = PracticeDataGenerator(
            num_test_runs=num_test_runs,
            num_tests_per_run=num_tests_per_run,
            num_sessions_per_run=num_sessions_per_run,
        )
        data = generator.generate()

        if output_file:
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2)
            console.print(f"Generated data saved to {output_file}")

        if load_to_profile:
            profile = get_active_profile()
            profile_manager = get_profile_manager()
            for test_run_id, test_run_data in data.items():
                for session_id, session_data in test_run_data.items():
                    profile_manager.add_session(
                        test_run_id=test_run_id,
                        session_id=session_id,
                        session_data=session_data,
                    )
            console.print(f"Generated data loaded to profile [bold]{profile.name}[/bold]")

        console.print(f"Generated {num_test_runs} test runs with {num_tests_per_run} tests each")
    except Exception as e:
        console.print(f"Error generating practice data: {str(e)}", style="red")
        console.print(traceback.format_exc(), style="red")


@app.command()
def version():
    """Show the version of pytest-insight."""
    from pytest_insight import __version__

    console = Console()
    console.print(f"pytest-insight version: {__version__}")


@app.callback()
def main():
    """Command-line interface for pytest-insight."""
    pass
