from __future__ import annotations

from typing import TYPE_CHECKING

import nbformat
from nbclient import NotebookClient

if TYPE_CHECKING:
    from pathlib import Path


def run_notebook(path: Path, cwd: Path) -> None:
    nb = nbformat.read(path, as_version=4)
    NotebookClient(nb, resources={"metadata": {"path": str(cwd)}}).execute(cwd=cwd)
