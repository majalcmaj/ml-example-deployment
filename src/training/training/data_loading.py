from __future__ import annotations

from typing import TYPE_CHECKING

from forecasting.csv_loading import load_csv_directory
from infra.logger import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd

log = get_logger(__name__)


def load_training_data(data_dir: Path) -> pd.DataFrame:
    raw_sales, csv_files = load_csv_directory(
        data_dir, transform=lambda frame, path: frame.assign(Source_File=path.name)
    )
    log.info("Loaded %s rows from %d file(s): %s", f"{len(raw_sales):,}", len(csv_files), [p.name for p in csv_files])
    log.debug(
        "Shape: %s | Columns: %s | Dtypes: %s | Missing values: %s | Duplicate rows: %s\n%s",
        raw_sales.shape,
        raw_sales.columns.tolist(),
        raw_sales.dtypes.to_dict(),
        raw_sales.isna().sum().to_dict(),
        raw_sales.duplicated().sum(),
        raw_sales.describe(include="all").transpose(),
    )
    return raw_sales
