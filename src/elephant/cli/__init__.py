"""Elephant CLI entry point."""

from __future__ import annotations

import argparse
import os
import sys


def main() -> None:
    """Main CLI dispatcher with subcommands."""
    parser = argparse.ArgumentParser(
        prog="elephant",
        description="My Little Elephant CLI",
    )
    parser.add_argument(
        "-c", "--config",
        default=os.environ.get("CONFIG_PATH", "config.yaml"),
        help="Path to config.yaml (default: $CONFIG_PATH or config.yaml)",
    )

    subparsers = parser.add_subparsers(dest="command")

    # debug-message subcommand
    dm = subparsers.add_parser(
        "debug-message",
        help="Run a message through the full flow without persisting anything",
    )
    dm.add_argument("message", help="The message text to process")
    dm.add_argument(
        "-d", "--database",
        default=None,
        help="Database name (default: first in config)",
    )

    # audit subcommand
    au = subparsers.add_parser(
        "audit",
        help="Run consistency checks on a database",
    )
    au.add_argument(
        "-d", "--database",
        default=None,
        help="Database name (default: first in config)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "debug-message":
        from elephant.cli.debug_message import run_debug_message

        run_debug_message(config_path=args.config, message=args.message, database=args.database)
    elif args.command == "audit":
        from elephant.cli.audit import run_audit_cli

        run_audit_cli(config_path=args.config, database=args.database)
