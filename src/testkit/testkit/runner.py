from __future__ import annotations

from typing import TYPE_CHECKING
import subprocess

if TYPE_CHECKING:
    from pathlib import Path


def run_script(path: Path, cwd: Path) -> None:
    subprocess.run(["uv", "run", "python3", str(path)], cwd=cwd, check=True)
