"""Command-line entry point for gator-hacks."""

from __future__ import annotations

import typer
from loguru import logger

from gator_hacks import hello

app = typer.Typer(help="gator-hacks CLI")


@app.command()
def hello_cmd() -> None:
    """Print the greeting."""
    logger.info(hello())


@app.command()
def version() -> None:
    """Print the package version."""
    from importlib.metadata import version

    logger.info(f"gator-hacks {version('gator-hacks')}")


def main() -> None:
    """Entry point for the ``gator-hacks`` console script."""
    app()


if __name__ == "__main__":
    main()
