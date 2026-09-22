from typing import TYPE_CHECKING, cast

from forecasting.artifacts import verify_artifacts_present
from forecasting.consts import METADATA_FILENAME, PREDICTED_QTY_COLUMN
from forecasting.features import build_future_features, encode_for_model
from forecasting.metadata import ForecastMetadata
from forecasting.model import make_forecast
from infra.context import init_context
from infra.metrics import LoggingMetricsSink, MetricsCollector

from inference.config import CONFIG
from inference.preprocess import payload_to_dataframe, preprocess_data
from inference.result_upload import upload_inference_results
from infra import logger

init_context()
from inference.gateway import RestGateway, SalesGateway
from inference.record_store import ForecastRecordStore, LocalForecastRecordStore

if TYPE_CHECKING:
    import pandas as pd

    from inference.config import Config


def _make_forecast_timed(
    config: Config,
    future_features: pd.DataFrame,
    X_future: pd.DataFrame,
    metadata: ForecastMetadata,
    metrics: MetricsCollector,
) -> pd.DataFrame:
    with metrics.timer("inference_duration_seconds"):
        return make_forecast(
            config.artifact_dir, future_features, X_future, metadata.configuration
        )


def _record_forecast_metrics(metrics: MetricsCollector, forecast: pd.DataFrame) -> None:
    metrics.record("forecast_rows", len(forecast))
    metrics.record(
        "forecast_total_units", cast("float", forecast[PREDICTED_QTY_COLUMN].sum())
    )


def _record_metadata_metrics(
    metrics: MetricsCollector, metadata: ForecastMetadata
) -> None:
    metrics.record("model_feature_count", len(metadata.model_feature_columns))
    metrics.record("category_count", len(metadata.categories))


def main(
    config: Config,
    sales_gateway: SalesGateway,
    record_store: ForecastRecordStore,
    metadata: ForecastMetadata,
    metrics: MetricsCollector,
) -> None:
    source_payload = sales_gateway.fetch_source_payload()
    recent_sales = payload_to_dataframe(source_payload)
    daily_sales = preprocess_data(metadata, recent_sales)

    future_features = build_future_features(metadata, daily_sales)
    X_future = encode_for_model(future_features, metadata)
    forecast_date = cast(
        "pd.Timestamp", future_features[metadata.configuration.date_column].max()
    )

    forecast = _make_forecast_timed(
        config, future_features, X_future, metadata, metrics
    )
    _record_forecast_metrics(metrics, forecast)

    upload_inference_results(sales_gateway, forecast_date, forecast, metadata)

    record_store.store(
        forecast_date.date(),
        cast(
            "pd.DataFrame",
            forecast[[metadata.configuration.category_column, PREDICTED_QTY_COLUMN]],
        ),
        source_payload,
    )


def run(
    config: Config,
    sales_gateway: SalesGateway,
    record_store: ForecastRecordStore,
    metrics: MetricsCollector,
) -> None:
    log = logger.get_logger(__name__)
    log.info("Running inference with config: %s", config.model_dump_json(indent=2))

    verify_artifacts_present(config.artifact_dir)

    metadata = ForecastMetadata.load(config.artifact_dir / METADATA_FILENAME)

    log.info(
        "Loaded model contract with %s features and %s categories.",
        len(metadata.model_feature_columns),
        len(metadata.categories),
    )
    _record_metadata_metrics(metrics, metadata)

    main(config, sales_gateway, record_store, metadata, metrics)


if __name__ == "__main__":
    with MetricsCollector(LoggingMetricsSink()) as metrics:
        run(CONFIG, RestGateway(CONFIG), LocalForecastRecordStore(CONFIG.output_dir), metrics)
