from typing import TYPE_CHECKING

import pandas as pd
from infra.logger import get_logger

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger(__name__)


# Note: this CSV glob+concat is similar to inference/gateway.py:111-115's, but deliberately left
# duplicated -- different semantics (full history + Source_File tag vs. recent window -> JSON
# records), ~6 lines, and sharing it would couple an app to an app.
def load_training_data(data_dir: Path) -> pd.DataFrame:
    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    frames = []
    for csv_file in csv_files:
        frame = pd.read_csv(csv_file)
        frame["Source_File"] = csv_file.name
        frames.append(frame)

    raw_sales = pd.concat(frames, ignore_index=True)
    log.info(f"Loaded {len(raw_sales):,} rows from {len(csv_files)} file(s):")
    log.info([path.name for path in csv_files])
    return raw_sales
