import subprocess  # nosec
import sys
from pathlib import Path

from fastdfs_client import __version__

if sys.version_info >= (3, 11):
    from contextlib import chdir

else:
    import contextlib
    import os

    class chdir(
        contextlib.AbstractContextManager
    ):  # Copied from source code of Python3.13
        """Non thread-safe context manager to change the current working directory."""

        def __init__(self, path) -> None:
            self.path = path
            self._old_cwd: list[str] = []

        def __enter__(self) -> None:
            self._old_cwd.append(os.getcwd())
            os.chdir(self.path)

        def __exit__(self, *excinfo) -> None:
            os.chdir(self._old_cwd.pop())


def _read_version():
    cmd = "poetry version -s"
    r = subprocess.run(cmd.split(), capture_output=True, encoding="utf-8")  # nosec
    return r.stdout.splitlines()[-1].strip()


def test_version():
    assert _read_version() == __version__


def test_added_by_poetry_v2(tmp_path: Path):
    tortoise_orm = Path(__file__).parent.resolve().parent
    with chdir(tmp_path):
        package = "foo"
        subprocess.run(["poetry", "new", package])  # nosec
        with chdir(package):
            r = subprocess.run(["poetry", "add", tortoise_orm])  # nosec
            assert r.returncode == 0
