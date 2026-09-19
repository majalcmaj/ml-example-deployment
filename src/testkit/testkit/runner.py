from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def run_script(path: Path, cwd: Path) -> None:
    subprocess.run(["uv", "run", "python3", str(path)], cwd=cwd, check=True)
