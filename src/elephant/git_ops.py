"""Git operations: init, auto-commit with conventional messages."""

import logging
import os
import subprocess
from datetime import date

from elephant.tracing import GitCommitStep, record_step

logger = logging.getLogger(__name__)


class GitRepo:
    """Git repository wrapper using subprocess (no GitPython dependency)."""

    def __init__(self, repo_dir: str) -> None:
        self.repo_dir = os.path.abspath(repo_dir)

    def _run(
        self, args: list[str], *, check: bool = True, capture: bool = True
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", self.repo_dir, *args],
            capture_output=capture,
            text=True,
            check=check,
        )

    def _is_own_repo(self) -> bool:
        """Check if repo_dir is the root of its own git repository."""
        result = self._run(
            ["rev-parse", "--show-toplevel"], check=False
        )
        if result.returncode != 0:
            return False
        toplevel = os.path.normpath(result.stdout.strip())
        return toplevel == os.path.normpath(self.repo_dir)

    def initialize(self) -> None:
        """Initialize git repo with initial commit. Idempotent."""
        if self._is_own_repo():
            logger.info("Git repo already initialized at %s", self.repo_dir)
            return

        self._run(["init"])
        self._run(["config", "user.name", "My Little Elephant"])
        self._run(["config", "user.email", "elephant@family.local"])
        self._run(["add", "."])
        self._run(["commit", "-m", "[init] Initial data structure"])
        logger.info("Git repo initialized at %s", self.repo_dir)

    def auto_commit(
        self,
        tag: str,
        message: str,
        timestamp: date | None = None,
        paths: list[str] | None = None,
    ) -> str | None:
        """Stage and commit with conventional message format.

        Format: [tag] message — YYYY-MM-DD
        Returns the commit SHA, or None if nothing changed.
        """
        if paths:
            for p in paths:
                self._run(["add", p])
        else:
            self._run(["add", "."])

        # Check if there's anything to commit
        result = self._run(["diff", "--cached", "--quiet"], check=False)
        if result.returncode == 0:
            logger.debug("Nothing to commit for [%s] %s", tag, message)
            return None

        date_str = (timestamp or date.today()).isoformat()
        commit_msg = f"[{tag}] {message} \u2014 {date_str}"
        self._run(["commit", "-m", commit_msg])

        sha_result = self._run(["rev-parse", "HEAD"])
        sha = sha_result.stdout.strip()
        logger.info("Committed: %s (%s)", commit_msg, sha[:8])

        record_step(GitCommitStep(sha=sha, message=commit_msg))

        return sha
