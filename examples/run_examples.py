import os
from pathlib import Path

import typer
from generate_example_data import ExampleDataGenerator


def main():
    """Run pytest-insight examples with demo data."""
    # Create example data file (not just directory)
    example_dir = Path.home() / ".pytest_insight_examples"
    example_file = example_dir / "example_sessions.json"

    # Set environment variable to use example storage
    os.environ["PYTEST_INSIGHT_STORAGE"] = str(example_file)

    # Generate example data
    generator = ExampleDataGenerator(example_file)
    generator.generate_example_data(num_days=30)

    # Show example commands
    typer.secho("\nExample commands to try:", fg=typer.colors.GREEN)
    examples = [
        "insight session show --sut api-service",
        "insight history list --by-sut --days 7",
        "insight analytics summary --warnings",
        "insight analytics failures api-service",
        "insight analytics compare api-service web-frontend --mode sut",
    ]

    for cmd in examples:
        typer.echo(f"  {cmd}")


if __name__ == "__main__":
    main()
