"""Tests for atomic file writes."""

import os

from elephant.atomic import atomic_write


def test_atomic_write_creates_file(tmp_path):
    path = str(tmp_path / "test.txt")
    atomic_write(path, "hello")
    assert os.path.exists(path)
    with open(path) as f:
        assert f.read() == "hello"


def test_atomic_write_overwrites(tmp_path):
    path = str(tmp_path / "test.txt")
    atomic_write(path, "first")
    atomic_write(path, "second")
    with open(path) as f:
        assert f.read() == "second"


def test_atomic_write_creates_parent_dirs(tmp_path):
    path = str(tmp_path / "a" / "b" / "test.txt")
    atomic_write(path, "nested")
    with open(path) as f:
        assert f.read() == "nested"


def test_atomic_write_no_leftover_temp_on_success(tmp_path):
    path = str(tmp_path / "test.txt")
    atomic_write(path, "content")
    files = os.listdir(tmp_path)
    assert files == ["test.txt"]


def test_atomic_write_empty_content(tmp_path):
    path = str(tmp_path / "empty.txt")
    atomic_write(path, "")
    with open(path) as f:
        assert f.read() == ""
