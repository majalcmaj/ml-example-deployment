from pathlib import Path

import nbformat
from nbclient import NotebookClient


def run_notebook(path: Path, cwd: Path) -> None:
    nb = nbformat.read(path, as_version=4)
    NotebookClient(nb, resources={"metadata": {"path": str(cwd)}}).execute(cwd=cwd)
