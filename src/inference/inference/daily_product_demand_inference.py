from typing import cast

import pandas as pd
from common.context import init_context
from common.forecast_metadata import ForecastMetadata
from common.preprocessing import (
    validate_required_columns_present,
)

from common import logger
from inference.config import CONFIG
from inference.features import reconstruct_training_features
from inference.forecaster import make_forecast
from inference.preprocess import payload_to_dataframe, preprocess_data
from inference.result_payload import CategoryPrediction, InferenceResultPayload

init_context()
from inference.gateway import SalesGateway, make_gateway

if __name__ == "__main__":
    log = logger.get_logger(__name__)
    log.info("Simulation mode: %s", CONFIG.simulation_mode)
    log.info("Requested history days: %s", CONFIG.history_days)

    ARTIFACT_DIR = CONFIG.artifact_dir
    if not ARTIFACT_DIR.exists():
        raise FileNotFoundError(
            "Could not find outputs/. Run training or deploy the model artifacts first."
        )

    metadata_path = ARTIFACT_DIR / "forecast_metadata.joblib"
    if not metadata_path.exists():
        raise FileNotFoundError(f"The metadata is missing from {ARTIFACT_DIR}.")

    metadata = ForecastMetadata.load(metadata_path)

    log.info(
        "Loaded model contract with %s features and %s categories.",
        len(metadata.model_feature_columns),
        len(metadata.categories),
    )

    sales_gateway = make_gateway(CONFIG)

    def obtain_recent_sales(sales_gateway: SalesGateway) -> pd.DataFrame:
        source_payload = sales_gateway.fetch_source_payload()
        return payload_to_dataframe(source_payload)

    recent_sales = obtain_recent_sales(sales_gateway)
    validate_required_columns_present(recent_sales)
    all_dates, latest_date, daily_sales = preprocess_data(metadata, recent_sales)

    log.info(
        "Prepared %d days through %s for %d categories.",
        len(all_dates),
        latest_date.date(),
        len(metadata.categories),
    )

    forecast_date, future_features, X_future = reconstruct_training_features(
        latest_date, metadata, daily_sales
    )

    forecast = make_forecast(
        ARTIFACT_DIR, future_features, X_future, metadata.configuration
    )

    log.info(forecast)
    log.info("Forecast total units: %d", forecast["Predicted_Qty"].sum())

    # ## 6. Return predictions to the result endpoint
    # Serialize the forecast as JSON and POST it in real mode. Simulation mode displays the request body without contacting an external service.

    result_payload = InferenceResultPayload(
        forecast_date=forecast_date.date(),
        generated_at_utc=pd.Timestamp.now(tz="UTC"),
        predictions=[
            CategoryPrediction(
                category=str(row[metadata.configuration.category_column]),
                predicted_quantity=int(cast("int", row["Predicted_Qty"])),
            )
            for _, row in forecast.iterrows()
        ],
    )

    sales_gateway.upload_inference_results(result_payload.model_dump(mode="json"))

    forecast[[metadata.configuration.category_column, "Predicted_Qty"]].to_csv(
        CONFIG.output_dir / "inference_next_day_forecast.csv", index=False
    )
