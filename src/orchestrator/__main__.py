"""Entry point for ``python -m orchestrator``."""

from __future__ import annotations

from orchestrator.cli import app


def main() -> None:
    """Launch the CLI."""
    app()


if __name__ == "__main__":
    main()
