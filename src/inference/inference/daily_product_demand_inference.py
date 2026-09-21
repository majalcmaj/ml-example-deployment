# # Daily product demand inference
#
# This notebook simulates the inference portion of the pipeline: obtain recent sales as JSON, reconstruct the training features, load the trained XGBoost model, predict the incoming day, and send the results to another API endpoint.
#
# Simulation mode is enabled by default. It converts the bundled CSV history to the same JSON contract and prints the outbound request instead of making network calls.

# ## 1. Configure runtime and API parameters
# Databricks job parameters are exposed as widgets. Credentials are read from Databricks Secrets only when real API mode is enabled.


from typing import cast

import pandas as pd
from common.context import init_context
from common.forecast_metadata import ForecastMetadata
from common.preprocessing import (
    aggregate_per_category,
    columns_to_expected_types,
    get_valid_date_target_array,
    validate_required_columns_present,
)

from common import logger
from inference.config import CONFIG
from inference.features import reconsturct_features
from inference.forecaster import make_forecast
from inference.preprocess import payload_to_dataframe
from inference.result_payload import CategoryPrediction, InferenceResultPayload

init_context()
log = logger.get_logger(__name__)
from inference.gateway import SalesGateway, make_gateway

log.info("Simulation mode: %s", CONFIG.simulation_mode)
log.info("Requested history days: %s", CONFIG.history_days)

ARTIFACT_DIR = CONFIG.artifact_dir
if not ARTIFACT_DIR.exists():
    raise FileNotFoundError(
        "Could not find outputs/. Run training or deploy the model artifacts first."
    )

# Metadata controls category names and exact feature ordering.
metadata_path = ARTIFACT_DIR / "forecast_metadata.joblib"
if not metadata_path.exists():
    raise FileNotFoundError(f"The metadata is missing from {ARTIFACT_DIR}.")

a = ForecastMetadata.load(metadata_path)
c = a.configuration

log.info(
    "Loaded model contract with %s features and %s categories.",
    len(a.model_feature_columns),
    len(a.categories),
)

sales_gateway = make_gateway(CONFIG)


def load_data(sales_gateway: SalesGateway) -> pd.DataFrame:
    source_payload = sales_gateway.fetch_source_payload()
    return payload_to_dataframe(source_payload)


recent_sales = load_data(sales_gateway)
validate_required_columns_present(recent_sales)


def preprocess_data(
    metadata: ForecastMetadata, sales: pd.DataFrame
) -> tuple[pd.DatetimeIndex, pd.Timestamp, pd.DataFrame]:
    """Normalize the response into one daily row per known category, fill absent date-category combinations with zero, and verify enough history exists for the model's 28-day features."""
    model_config = metadata.configuration
    sales = columns_to_expected_types(sales)

    valid_rows = get_valid_date_target_array(sales)
    valid_rows &= sales[model_config.category_column].isin(a.categories)
    sales = sales.loc[
        valid_rows,
        [
            model_config.date_column,
            model_config.category_column,
            model_config.target_column,
        ],
    ]

    target_sums = cast(
        "pd.Series",
        sales.groupby([model_config.date_column, model_config.category_column])[
            model_config.target_column
        ].sum(),
    )
    daily_sales = target_sums.reset_index().sort_values(
        [model_config.category_column, model_config.date_column]
    )
    if daily_sales.empty:
        raise ValueError(
            "No sales history available after filtering to known categories."
        )
    latest_date = cast("pd.Timestamp", daily_sales[model_config.date_column].max())
    first_required_date = latest_date - pd.Timedelta(days=27)
    if daily_sales[model_config.date_column].min() > first_required_date:
        raise ValueError(
            "At least 28 consecutive calendar days of history are required for inference."
        )

    all_dates = pd.date_range(
        daily_sales[model_config.date_column].min(), latest_date, freq="D"
    )
    complete_index = pd.MultiIndex.from_product(
        [all_dates, a.categories],
        names=[model_config.date_column, model_config.category_column],
    )
    daily_sales = aggregate_per_category(complete_index, daily_sales)
    return all_dates, latest_date, daily_sales


all_dates, latest_date, daily_sales = preprocess_data(a, recent_sales)


log.info(
    "Prepared %d days through %s for %d categories.",
    len(all_dates),
    latest_date.date(),
    len(a.categories),
)


forecast_date, future_features, X_future = reconsturct_features(
    latest_date, a, daily_sales
)


forecast = make_forecast(ARTIFACT_DIR, future_features, X_future, c)

log.info(forecast)
log.info("Forecast total units: %d", forecast["Predicted_Qty"].sum())

# ## 6. Return predictions to the result endpoint
# Serialize the forecast as JSON and POST it in real mode. Simulation mode displays the request body without contacting an external service.

result_payload = InferenceResultPayload(
    forecast_date=forecast_date.date(),
    generated_at_utc=pd.Timestamp.now(tz="UTC"),
    predictions=[
        CategoryPrediction(
            category=str(row[c.category_column]),
            predicted_quantity=int(cast("int", row["Predicted_Qty"])),
        )
        for _, row in forecast.iterrows()
    ],
)

sales_gateway.upload_inference_results(result_payload.model_dump(mode="json"))

forecast[[c.category_column, "Predicted_Qty"]].to_csv(
    CONFIG.output_dir / "inference_next_day_forecast.csv", index=False
)
