from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def load_csv_directory(
    data_dir: Path,
    transform: Callable[[pd.DataFrame, Path], pd.DataFrame] | None = None,
) -> tuple[pd.DataFrame, list[Path]]:
    """Read every CSV in `data_dir`, optionally transforming each frame, and concat them."""
    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    frames = []
    for csv_file in csv_files:
        frame = pd.read_csv(csv_file)
        if transform is not None:
            frame = transform(frame, csv_file)
        frames.append(frame)

    return pd.concat(frames, ignore_index=True), csv_files
