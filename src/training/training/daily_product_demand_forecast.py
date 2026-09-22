from typing import TYPE_CHECKING, cast

import pandas as pd
from forecasting.consts import (
    CATEGORY_COLUMN,
    DATE_COLUMN,
    METADATA_FILENAME,
    TARGET_COLUMN,
)
from forecasting.features import (
    build_future_features,
    create_time_features,
    encode_for_model,
)
from forecasting.metadata import ForecastMetadata, ModelConfiguration
from forecasting.model import make_forecast, save_model
from infra.logger import get_logger

from training.config import CONFIG
from training.data_loading import load_training_data
from training.dataset import encode_train_validation, split_train_validation
from training.evaluate import evaluate_predictions
from training.outliers import IS_OUTLIER_COLUMN, flag_outliers
from training.preprocess import build_daily_panel, clean_sales
from training.train_model import fit_model

if TYPE_CHECKING:
    from training.config import Config

RANDOM_SEED = 42
VALIDATION_DAYS = 30  # TODO: move to configuration


# TODO: split it further - it should have clearly named train/fit/whatever + validate functions that it just calls
def run(config: Config) -> None:

    log = get_logger(__name__)

    raw_sales = load_training_data(config.data_dir)

    sales = clean_sales(raw_sales)
    # TODO: see my comment in data_loading. Move the logs into the functions, compact them and split - important stuff to info level, less important to debug.
    log.info(
        f"Removed {len(raw_sales) - len(sales):,} exact duplicate or invalid rows."
    )
    log.info(
        f"Clean date range: {sales[DATE_COLUMN].min().date()} to {sales[DATE_COLUMN].max().date()}"
    )
    log.info(f"Product categories: {sales[CATEGORY_COLUMN].nunique()}")

    daily_sales, all_categories = build_daily_panel(sales)
    log.info(
        f"Complete panel: {daily_sales[DATE_COLUMN].nunique()} days x "
        f"{len(all_categories)} categories = {len(daily_sales):,} rows"
    )
    log.info(daily_sales.head())

    # TODO: I also want this moved to some utility functions - do not mix abstraction levels, as per clean code guidelines.
    validation_start = daily_sales[DATE_COLUMN].max() - pd.Timedelta(
        days=VALIDATION_DAYS - 1
    )
    daily_sales, category_quartiles = flag_outliers(
        daily_sales, validation_start, CATEGORY_COLUMN, DATE_COLUMN, TARGET_COLUMN
    )
    log.info(
        f"Training outliers marked for removal: {daily_sales[IS_OUTLIER_COLUMN].sum():,}"
    )
    log.info(category_quartiles.head())

    featured_sales = create_time_features(daily_sales)
    # TODO: Ditto - mixing abstraction levels
    history_features = [
        column
        for column in featured_sales.columns
        if column.startswith(("Lag_", "Rolling_"))
    ]
    featured_sales = featured_sales.dropna(subset=history_features).reset_index(
        drop=True
    )
    log.info(
        f"Rows available after 28 days of feature history: {len(featured_sales):,}"
    )
    log.info(featured_sales.head())

    feature_columns = [
        CATEGORY_COLUMN,
        "Day_Of_Week",
        "Month",
        "Day_Of_Month",
        "Day_Of_Year",
        "Is_Weekend",
        *history_features,
    ]
    train_data, validation_data = split_train_validation(
        featured_sales, validation_start, DATE_COLUMN
    )
    X_train, X_validation = encode_train_validation(
        train_data, validation_data, feature_columns, CATEGORY_COLUMN
    )
    # TODO: is there a way to avoid casting here? Maybe make train_data a pydantic model? or at least namedtuple?
    y_train = cast("pd.Series", train_data[TARGET_COLUMN])
    y_validation = cast("pd.Series", validation_data[TARGET_COLUMN])
    log.info(
        f"Training: {train_data[DATE_COLUMN].min().date()} to {train_data[DATE_COLUMN].max().date()}, {len(train_data):,} rows"
    )
    log.info(
        f"Validation: {validation_data[DATE_COLUMN].min().date()} to {validation_data[DATE_COLUMN].max().date()}, {len(validation_data):,} rows"
    )
    log.info("Model features: %s", X_train.shape[1])

    model = fit_model(X_train, y_train, X_validation, y_validation, RANDOM_SEED)
    log.info("Model training complete.")

    # TODO: Why do we pass constatnts as arguments? Can we use them directly?
    overall_metrics, category_metrics = evaluate_predictions(
        validation_data,
        X_validation,
        model,
        DATE_COLUMN,
        CATEGORY_COLUMN,
        TARGET_COLUMN,
    )
    log.info(overall_metrics.to_frame())
    log.info(category_metrics)

    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    save_model(model, output_dir)

    metadata = ForecastMetadata(
        model_feature_columns=X_train.columns.tolist(),
        raw_feature_columns=feature_columns,
        categories=all_categories,
        category_dummy_columns=[
            column
            for column in X_train.columns
            if column.startswith(f"{CATEGORY_COLUMN}_")
        ],
        configuration=ModelConfiguration(
            date_column=DATE_COLUMN,
            category_column=CATEGORY_COLUMN,
            target_column=TARGET_COLUMN,
            validation_days=VALIDATION_DAYS,
            random_seed=RANDOM_SEED,
        ),
        outlier_bounds=category_quartiles.reset_index(),
        validation_metrics=overall_metrics.to_dict(),
    )
    metadata.save(output_dir / METADATA_FILENAME)

    latest_date = cast("pd.Timestamp", daily_sales[DATE_COLUMN].max())
    future_features = build_future_features(latest_date, metadata, daily_sales)
    X_future = encode_for_model(future_features, metadata)
    forecast = make_forecast(
        output_dir, future_features, X_future, metadata.configuration
    )
    forecast.to_csv(output_dir / "next_day_product_forecast.csv", index=False)

    log.info("Saved predictions, model, and metadata to: %s", output_dir)
    log.info(metadata)


if __name__ == "__main__":
    run(CONFIG)
