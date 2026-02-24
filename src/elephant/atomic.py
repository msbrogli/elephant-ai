"""Atomic file write: write-to-temp, fsync, rename."""

import contextlib
import os
import tempfile


def atomic_write(path: str, content: str) -> None:
    """Write content to path atomically.

    Uses mkstemp in the same directory, writes, fsyncs, then renames.
    This guarantees that readers either see the old file or the complete new file.
    """
    path = os.path.abspath(path)
    dir_path = os.path.dirname(path)
    os.makedirs(dir_path, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dir_path, prefix=".tmp_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp_path, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
