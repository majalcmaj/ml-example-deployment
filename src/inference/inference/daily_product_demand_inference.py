from typing import TYPE_CHECKING

from common.context import init_context
from common.forecast_metadata import ForecastMetadata

from common import logger
from inference.config import CONFIG
from inference.features import reconstruct_training_features
from inference.forecaster import make_forecast
from inference.model_loader import MODEL_FILENAME
from inference.preprocess import payload_to_dataframe, preprocess_data
from inference.result_upload import upload_inference_results

init_context()
from inference.gateway import SalesGateway, make_gateway

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd

    from inference.config import Config

METADATA_FILENAME = "forecast_metadata.joblib"


def _obtain_recent_sales(sales_gateway: SalesGateway) -> pd.DataFrame:
    source_payload = sales_gateway.fetch_source_payload()
    return payload_to_dataframe(source_payload)


def verify_artifacts_present(artifact_dir: Path) -> None:
    """Fail fast on missing model/metadata artifacts, before any network call or
    feature reconstruction runs."""
    if not artifact_dir.exists():
        raise FileNotFoundError(
            "Could not find outputs/. Run training or deploy the model artifacts first."
        )

    missing = [
        filename
        for filename in (METADATA_FILENAME, MODEL_FILENAME)
        if not (artifact_dir / filename).exists()
    ]
    if missing:
        raise FileNotFoundError(
            f"Missing required artifact(s) in {artifact_dir}: {', '.join(missing)}."
        )


def main(
    config: Config, sales_gateway: SalesGateway, metadata: ForecastMetadata
) -> None:
    recent_sales = _obtain_recent_sales(sales_gateway)
    latest_date, daily_sales = preprocess_data(metadata, recent_sales)

    forecast_date, future_features, X_future = reconstruct_training_features(
        latest_date, metadata, daily_sales
    )

    forecast = make_forecast(
        config.artifact_dir, future_features, X_future, metadata.configuration
    )

    upload_inference_results(sales_gateway, forecast_date, forecast, metadata)

    forecast[[metadata.configuration.category_column, "Predicted_Qty"]].to_csv(
        config.output_dir / "inference_next_day_forecast.csv", index=False
    )


if __name__ == "__main__":
    log = logger.get_logger(__name__)
    log.info("Running inference with config: %s", CONFIG.model_dump_json(indent=2))

    verify_artifacts_present(CONFIG.artifact_dir)

    loaded_metadata = ForecastMetadata.load(CONFIG.artifact_dir / METADATA_FILENAME)

    log.info(
        "Loaded model contract with %s features and %s categories.",
        len(loaded_metadata.model_feature_columns),
        len(loaded_metadata.categories),
    )

    main(CONFIG, make_gateway(CONFIG), loaded_metadata)
