"""audit subcommand: run consistency checks on a database."""

from __future__ import annotations

import sys

from elephant.audit import run_audit
from elephant.config import load_config
from elephant.data.store import DataStore


def run_audit_cli(config_path: str, database: str | None) -> None:
    """Load config, init store, run audit, print report."""
    config = load_config(config_path)

    if database:
        db_cfg = None
        for db in config.databases:
            if db.name == database:
                db_cfg = db
                break
        if db_cfg is None:
            names = ", ".join(db.name for db in config.databases)
            print(f"Error: database '{database}' not found. Available: {names}", file=sys.stderr)
            sys.exit(1)
    else:
        db_cfg = config.databases[0]

    store = DataStore(db_cfg.data_dir)
    report = run_audit(store)

    if not report.issues:
        print("No issues found.")
        return

    for issue in report.issues:
        severity = issue.severity.upper()
        print(f"[{severity}] {issue.category}: {issue.message}")

    print(f"\nSummary: {report.error_count} error(s), {report.warning_count} warning(s)")
    sys.exit(1 if report.error_count > 0 else 0)
