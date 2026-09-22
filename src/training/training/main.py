from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

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
    history_feature_columns,
)
from forecasting.metadata import ForecastMetadata, ModelConfiguration
from forecasting.model import make_forecast, save_model
from infra.context import init_context
from infra.logger import get_logger
from infra.metrics import LoggingMetricsSink, MetricsCollector

init_context()

from training.config import CONFIG
from training.data_loading import load_training_data
from training.dataset import (
    compute_validation_start,
    prepare_train_validation,
    split_train_validation,
)
from training.evaluate import evaluate_predictions
from training.outliers import IS_OUTLIER_COLUMN, flag_outliers
from training.preprocess import build_daily_panel, clean_sales
from training.train_model import fit_model

if TYPE_CHECKING:
    import pandas as pd
    from xgboost import XGBRegressor

    from training.config import Config

RANDOM_SEED = 42

log = get_logger(__name__)


@dataclass
class PreparedData:
    daily_sales: pd.DataFrame
    all_categories: list[str]
    category_quartiles: pd.DataFrame
    feature_columns: list[str]
    train_data: pd.DataFrame
    validation_data: pd.DataFrame
    X_train: pd.DataFrame
    X_validation: pd.DataFrame
    y_train: pd.Series
    y_validation: pd.Series


@dataclass
class TrainedModel:
    model: XGBRegressor
    overall_metrics: pd.Series
    category_metrics: pd.DataFrame


def _prepare_data(config: Config) -> PreparedData:
    raw_sales = load_training_data(config.data_dir)
    sales = clean_sales(raw_sales)
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

    validation_start = compute_validation_start(
        daily_sales, config.validation_days, DATE_COLUMN
    )
    daily_sales, category_quartiles = flag_outliers(
        daily_sales, validation_start, CATEGORY_COLUMN, DATE_COLUMN, TARGET_COLUMN
    )
    log.info(
        f"Training outliers marked for removal: {daily_sales[IS_OUTLIER_COLUMN].sum():,}"
    )

    featured_sales = create_time_features(daily_sales)
    history_features = history_feature_columns(featured_sales)
    featured_sales = featured_sales.dropna(subset=history_features).reset_index(
        drop=True
    )
    log.info(
        f"Rows available after 28 days of feature history: {len(featured_sales):,}"
    )

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
    split = prepare_train_validation(
        train_data, validation_data, feature_columns, CATEGORY_COLUMN, TARGET_COLUMN
    )
    log.info(
        f"Training: {train_data[DATE_COLUMN].min().date()} to {train_data[DATE_COLUMN].max().date()}, {len(train_data):,} rows"
    )
    log.info(
        f"Validation: {validation_data[DATE_COLUMN].min().date()} to {validation_data[DATE_COLUMN].max().date()}, {len(validation_data):,} rows"
    )
    log.info("Model features: %s", split.X_train.shape[1])

    return PreparedData(
        daily_sales=daily_sales,
        all_categories=all_categories,
        category_quartiles=category_quartiles,
        feature_columns=feature_columns,
        train_data=train_data,
        validation_data=validation_data,
        X_train=split.X_train,
        X_validation=split.X_validation,
        y_train=split.y_train,
        y_validation=split.y_validation,
    )


def _fit_model_timed(prepared: PreparedData, metrics: MetricsCollector) -> XGBRegressor:
    with metrics.timer("training_duration_seconds"):
        return fit_model(
            prepared.X_train,
            prepared.y_train,
            prepared.X_validation,
            prepared.y_validation,
            RANDOM_SEED,
        )


def _record_evaluation_metrics(
    metrics: MetricsCollector, overall_metrics: pd.Series, train_rows: int
) -> None:
    metrics.record("validation_mae", cast("float", overall_metrics["MAE"]))
    metrics.record("validation_rmse", cast("float", overall_metrics["RMSE"]))
    metrics.record(
        "validation_wmape_percent", cast("float", overall_metrics["WMAPE_Percent"])
    )
    metrics.record("train_rows", train_rows)


def _train_and_evaluate(
    prepared: PreparedData, metrics: MetricsCollector
) -> TrainedModel:
    model = _fit_model_timed(prepared, metrics)
    log.info("Model training complete.")

    overall_metrics, category_metrics = evaluate_predictions(
        prepared.validation_data, prepared.X_validation, model
    )
    log.info(overall_metrics.to_frame())
    log.info(category_metrics)

    _record_evaluation_metrics(metrics, overall_metrics, len(prepared.train_data))

    return TrainedModel(
        model=model, overall_metrics=overall_metrics, category_metrics=category_metrics
    )


def _persist_outputs(
    config: Config, prepared: PreparedData, trained: TrainedModel
) -> None:
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    save_model(trained.model, output_dir)

    metadata = ForecastMetadata(
        model_feature_columns=prepared.X_train.columns.tolist(),
        raw_feature_columns=prepared.feature_columns,
        categories=prepared.all_categories,
        category_dummy_columns=[
            column
            for column in prepared.X_train.columns
            if column.startswith(f"{CATEGORY_COLUMN}_")
        ],
        configuration=ModelConfiguration(
            date_column=DATE_COLUMN,
            category_column=CATEGORY_COLUMN,
            target_column=TARGET_COLUMN,
            validation_days=config.validation_days,
            random_seed=RANDOM_SEED,
        ),
        outlier_bounds=prepared.category_quartiles.reset_index(),
        validation_metrics=trained.overall_metrics.to_dict(),
    )
    metadata.save(output_dir / METADATA_FILENAME)

    future_features = build_future_features(metadata, prepared.daily_sales)
    X_future = encode_for_model(future_features, metadata)
    forecast = make_forecast(
        output_dir, future_features, X_future, metadata.configuration
    )
    forecast.to_csv(output_dir / "next_day_product_forecast.csv", index=False)

    log.info("Saved predictions, model, and metadata to: %s", output_dir)
    log.info(metadata)


def run(config: Config, metrics: MetricsCollector) -> None:
    prepared = _prepare_data(config)
    trained = _train_and_evaluate(prepared, metrics)
    _persist_outputs(config, prepared, trained)


if __name__ == "__main__":
    with MetricsCollector(LoggingMetricsSink()) as metrics:
        run(CONFIG, metrics)
