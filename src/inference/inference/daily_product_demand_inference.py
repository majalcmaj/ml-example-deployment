from typing import TYPE_CHECKING, cast

from forecasting.artifacts import verify_artifacts_present
from forecasting.consts import METADATA_FILENAME
from forecasting.features import build_future_features, encode_for_model
from forecasting.metadata import ForecastMetadata
from forecasting.model import make_forecast
from infra.context import init_context

from inference.config import CONFIG
from inference.preprocess import payload_to_dataframe, preprocess_data
from inference.result_upload import upload_inference_results
from infra import logger

init_context()
from inference.gateway import RestGateway, SalesGateway

if TYPE_CHECKING:
    import pandas as pd

    from inference.config import Config


def _obtain_recent_sales(sales_gateway: SalesGateway) -> pd.DataFrame:
    source_payload = sales_gateway.fetch_source_payload()
    return payload_to_dataframe(source_payload)


def main(
    config: Config, sales_gateway: SalesGateway, metadata: ForecastMetadata
) -> None:
    recent_sales = _obtain_recent_sales(sales_gateway)
    daily_sales = preprocess_data(metadata, recent_sales)
    latest_date = cast(
        "pd.Timestamp", daily_sales[metadata.configuration.date_column].max()
    )

    future_features = build_future_features(latest_date, metadata, daily_sales)
    X_future = encode_for_model(future_features, metadata)
    forecast_date = cast(
        "pd.Timestamp", future_features[metadata.configuration.date_column].max()
    )

    forecast = make_forecast(
        config.artifact_dir, future_features, X_future, metadata.configuration
    )

    upload_inference_results(sales_gateway, forecast_date, forecast, metadata)

    forecast[[metadata.configuration.category_column, "Predicted_Qty"]].to_csv(
        config.output_dir / "inference_next_day_forecast.csv", index=False
    )


def run(config: Config, sales_gateway: SalesGateway) -> None:
    log = logger.get_logger(__name__)
    log.info("Running inference with config: %s", config.model_dump_json(indent=2))

    verify_artifacts_present(config.artifact_dir)

    metadata = ForecastMetadata.load(config.artifact_dir / METADATA_FILENAME)

    log.info(
        "Loaded model contract with %s features and %s categories.",
        len(metadata.model_feature_columns),
        len(metadata.categories),
    )

    main(config, sales_gateway, metadata)


if __name__ == "__main__":
    run(CONFIG, RestGateway(CONFIG))
