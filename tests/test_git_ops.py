"""Tests for git operations."""

import os
import subprocess
from datetime import date

from elephant.git_ops import GitRepo


def _git(repo_dir, *args):
    return subprocess.run(
        ["git", "-C", repo_dir, *args],
        capture_output=True,
        text=True,
        check=True,
    )


class TestGitInit:
    def test_initialize_creates_repo(self, tmp_path):
        repo_dir = str(tmp_path / "data")
        os.makedirs(repo_dir)
        # Create a file so there's something to commit
        with open(os.path.join(repo_dir, "test.txt"), "w") as f:
            f.write("hello")

        git = GitRepo(repo_dir)
        git.initialize()

        assert os.path.isdir(os.path.join(repo_dir, ".git"))
        log = _git(repo_dir, "log", "--oneline")
        assert "[init]" in log.stdout

    def test_initialize_idempotent(self, tmp_path):
        repo_dir = str(tmp_path / "data")
        os.makedirs(repo_dir)
        with open(os.path.join(repo_dir, "test.txt"), "w") as f:
            f.write("hello")

        git = GitRepo(repo_dir)
        git.initialize()
        git.initialize()  # should not error

        log = _git(repo_dir, "log", "--oneline")
        # Only one initial commit
        assert log.stdout.strip().count("\n") == 0


class TestAutoCommit:
    def _setup_repo(self, tmp_path):
        repo_dir = str(tmp_path / "data")
        os.makedirs(repo_dir)
        with open(os.path.join(repo_dir, "init.txt"), "w") as f:
            f.write("init")
        git = GitRepo(repo_dir)
        git.initialize()
        return repo_dir, git

    def test_auto_commit_with_changes(self, tmp_path):
        repo_dir, git = self._setup_repo(tmp_path)

        with open(os.path.join(repo_dir, "event.yaml"), "w") as f:
            f.write("id: test")

        sha = git.auto_commit("event", "Test event", timestamp=date(2026, 2, 24))
        assert sha is not None
        assert len(sha) == 40

        log = _git(repo_dir, "log", "--oneline", "-1")
        assert "[event] Test event" in log.stdout
        assert "2026-02-24" in log.stdout

    def test_auto_commit_no_changes(self, tmp_path):
        repo_dir, git = self._setup_repo(tmp_path)
        sha = git.auto_commit("test", "No changes")
        assert sha is None

    def test_auto_commit_uses_today_by_default(self, tmp_path):
        repo_dir, git = self._setup_repo(tmp_path)

        with open(os.path.join(repo_dir, "new.txt"), "w") as f:
            f.write("new")

        sha = git.auto_commit("test", "Today's commit")
        assert sha is not None

        log = _git(repo_dir, "log", "--oneline", "-1")
        assert date.today().isoformat() in log.stdout

    def test_auto_commit_specific_paths(self, tmp_path):
        repo_dir, git = self._setup_repo(tmp_path)

        with open(os.path.join(repo_dir, "a.txt"), "w") as f:
            f.write("a")
        with open(os.path.join(repo_dir, "b.txt"), "w") as f:
            f.write("b")

        sha = git.auto_commit("test", "Only a", paths=[os.path.join(repo_dir, "a.txt")])
        assert sha is not None

        # b.txt should still be untracked
        status = _git(repo_dir, "status", "--porcelain")
        assert "b.txt" in status.stdout

    def test_auto_commit_em_dash_format(self, tmp_path):
        repo_dir, git = self._setup_repo(tmp_path)

        with open(os.path.join(repo_dir, "test.yaml"), "w") as f:
            f.write("test")

        sha = git.auto_commit("morning", "Digest sent", timestamp=date(2026, 2, 24))
        assert sha is not None

        log = _git(repo_dir, "log", "-1", "--format=%s")
        assert log.stdout.strip() == "[morning] Digest sent \u2014 2026-02-24"
