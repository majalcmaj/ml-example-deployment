# # Daily product demand inference
#
# This notebook simulates the inference portion of the pipeline: obtain recent sales as JSON, reconstruct the training features, load the trained XGBoost model, predict the incoming day, and send the results to another API endpoint.
#
# Simulation mode is enabled by default. It converts the bundled CSV history to the same JSON contract and prints the outbound request instead of making network calls.

# ## 1. Configure runtime and API parameters
# Databricks job parameters are exposed as widgets. Credentials are read from Databricks Secrets only when real API mode is enabled.

import numpy as np
import pandas as pd
from common.context import init_context
from common.features import create_time_features
from common.forecast_metadata import ForecastMetadata, ModelConfiguration
from common.preprocessing import (
    aggregate_per_category,
    columns_to_expected_types,
    get_valid_date_target_array,
    validate_required_columns_present,
)

from common import logger
from inference.config import CONFIG
from inference.model_loader import load_model
from inference.preprocess import payload_to_dataframe

init_context()
log = logger.get_logger(__name__)
from inference.gateway import make_gateway

log.info("Simulation mode: %s", CONFIG.simulation_mode)
log.info("Requested history days: %s", CONFIG.history_days)

sales_gateway = make_gateway(CONFIG)
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

# Normalize the response into one daily row per known category, fill absent date-category combinations with zero, and verify enough history exists for the model's 28-day features.
source_payload = sales_gateway.fetch_source_payload()
recent_sales = payload_to_dataframe(source_payload)
validate_required_columns_present(recent_sales)
recent_sales = columns_to_expected_types(recent_sales)

valid_rows = get_valid_date_target_array(recent_sales)
valid_rows &= recent_sales[c.category_column].isin(a.categories)
recent_sales = recent_sales.loc[
    valid_rows, [c.date_column, c.category_column, c.target_column]
]

daily_sales = (
    recent_sales.groupby([c.date_column, c.category_column], as_index=False)[
        c.target_column
    ]
    .sum()
    .sort_values([c.category_column, c.date_column])
)
latest_date = daily_sales[c.date_column].max()
first_required_date = latest_date - pd.Timedelta(days=27)
if daily_sales[c.date_column].min() > first_required_date:
    raise ValueError(
        "At least 28 consecutive calendar days of history are required for inference."
    )

all_dates = pd.date_range(daily_sales[c.date_column].min(), latest_date, freq="D")
complete_index = pd.MultiIndex.from_product(
    [all_dates, a.categories], names=[c.date_column, c.category_column]
)
daily_sales = aggregate_per_category(complete_index, daily_sales)

log.info(
    "Prepared %d days through %s for %d categories.",
    len(all_dates),
    latest_date.date(),
    len(a.categories),
)

# ## 5. Reconstruct features and run inference
# Append the incoming day and calculate calendar, lag, and rolling features exactly as in training. Align the encoded columns to the stored model contract before predicting.

forecast_date = latest_date + pd.Timedelta(days=1)
future_rows = pd.DataFrame(
    {
        c.date_column: forecast_date,
        c.category_column: a.categories,
        c.target_column: 0.0,
    }
)
history_and_future = pd.concat([daily_sales, future_rows], ignore_index=True)
future_features = create_time_features(history_and_future)
future_features = future_features.loc[
    future_features[c.date_column] == forecast_date
].copy()

X_future = pd.get_dummies(
    future_features[a.raw_feature_columns], columns=[c.category_column], dtype=int
)
X_future = X_future.reindex(columns=a.model_feature_columns, fill_value=0)
if X_future.isna().any().any():
    raise ValueError(
        "Recent sales did not provide enough history to calculate every model feature."
    )


def make_forecast(c: ModelConfiguration) -> pd.DataFrame:
    model = load_model(ARTIFACT_DIR)
    predicted_quantities = np.rint(np.clip(model.predict(X_future), 0, None)).astype(
        int
    )
    forecast = future_features[[c.date_column, c.category_column]].copy()
    forecast["Predicted_Qty"] = predicted_quantities
    return forecast.sort_values(c.category_column).reset_index(drop=True)


forecast = make_forecast(c)

log.info(forecast)
log.info("Forecast total units: %d", forecast["Predicted_Qty"].sum())

# ## 6. Return predictions to the result endpoint
# Serialize the forecast as JSON and POST it in real mode. Simulation mode displays the request body without contacting an external service.

# TODO: pydantic validation
result_payload = {
    "forecast_date": forecast_date.strftime("%Y-%m-%d"),
    "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
    "predictions": [
        {
            "category": row[c.category_column],
            "predicted_quantity": int(row["Predicted_Qty"]),
        }
        for _, row in forecast.iterrows()
    ],
}
sales_gateway.upload_inference_results(result_payload)

forecast[[c.category_column, "Predicted_Qty"]].to_csv(
    CONFIG.output_dir / "inference_next_day_forecast.csv", index=False
)
