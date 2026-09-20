# # Daily product demand inference
#
#
#
# This notebook simulates the inference portion of the pipeline: obtain recent sales as JSON, reconstruct the training features, load the trained XGBoost model, predict the incoming day, and send the results to another API endpoint.
#
#
#
# Simulation mode is enabled by default. It converts the bundled CSV history to the same JSON contract and prints the outbound request instead of making network calls.

# ## 1. Configure runtime and API parameters
#
#
#
# Databricks job parameters are exposed as widgets. Credentials are read from Databricks Secrets only when real API mode is enabled.

# In[1]:


import joblib
import numpy as np
import pandas as pd
from common.context import init_context
from common.features import create_time_features
from common.preprocessing import (
    aggregate_per_category,
    columns_to_expected_types,
    get_valid_date_target_array,
    validate_required_columns_present,
)
from xgboost import XGBRegressor

from common import logger
from inference.config import CONFIG
from inference.preprocess import payload_to_dataframe

init_context()
log = logger.get_logger(__name__)
from inference.gateway import make_gateway

log.info("Simulation mode: %s", CONFIG.simulation_mode)
log.info("Requested history days: %s", CONFIG.history_days)

sales_gateway = make_gateway(CONFIG)

# ## 2. Load the trained model contract
#
#
#
# Load the XGBoost model and metadata written by the training notebook. Metadata controls category names and exact feature ordering.

# In[2]:

ARTIFACT_DIR = CONFIG.artifact_dir

if not ARTIFACT_DIR.exists():
    raise FileNotFoundError(
        "Could not find outputs/. Run training or deploy the model artifacts first."
    )


model_path = ARTIFACT_DIR / "xgb_daily_product_demand.json"

metadata_path = ARTIFACT_DIR / "forecast_metadata.joblib"

if not model_path.exists() or not metadata_path.exists():
    raise FileNotFoundError(
        "The trained model or forecast metadata is missing from outputs/."
    )


artifacts = joblib.load(metadata_path)

configuration = artifacts["configuration"]

DATE_COLUMN = configuration["date_column"]

CATEGORY_COLUMN = configuration["category_column"]

TARGET_COLUMN = configuration["target_column"]

MODEL_COLUMNS = artifacts["model_feature_columns"]

KNOWN_CATEGORIES = artifacts["categories"]


model = XGBRegressor()

model.load_model(model_path)

log.info(
    "Loaded model contract with %s features and %s categories.",
    len(MODEL_COLUMNS),
    len(KNOWN_CATEGORIES),
)


# ## 3. Query the recent-sales endpoint
#
#
#
# Real mode sends an authenticated GET request and expects either a JSON list or an object containing `records` or `data`. Simulation mode creates the same payload from the latest bundled CSV records. The endpoint must supply at least 28 calendar days of history.

# In[3]:
source_payload = sales_gateway.fetch_source_payload()

# ## 4. Validate and preprocess the JSON response
#
#
#
# Normalize the response into one daily row per known category, fill absent date-category combinations with zero, and verify enough history exists for the model's 28-day features.

# In[4]:

recent_sales = payload_to_dataframe(source_payload)

# In[10]:

validate_required_columns_present(recent_sales)
recent_sales = columns_to_expected_types(recent_sales)

valid_rows = get_valid_date_target_array(recent_sales)
valid_rows &= recent_sales[CATEGORY_COLUMN].isin(KNOWN_CATEGORIES)

recent_sales = recent_sales.loc[
    valid_rows, [DATE_COLUMN, CATEGORY_COLUMN, TARGET_COLUMN]
]

daily_sales = (
    recent_sales.groupby([DATE_COLUMN, CATEGORY_COLUMN], as_index=False)[TARGET_COLUMN]
    .sum()
    .sort_values([CATEGORY_COLUMN, DATE_COLUMN])
)

latest_date = daily_sales[DATE_COLUMN].max()

first_required_date = latest_date - pd.Timedelta(days=27)

if daily_sales[DATE_COLUMN].min() > first_required_date:
    raise ValueError(
        "At least 28 consecutive calendar days of history are required for inference."
    )

all_dates = pd.date_range(daily_sales[DATE_COLUMN].min(), latest_date, freq="D")

complete_index = pd.MultiIndex.from_product(
    [all_dates, KNOWN_CATEGORIES], names=[DATE_COLUMN, CATEGORY_COLUMN]
)
daily_sales = aggregate_per_category(complete_index, daily_sales)

log.info(
    "Prepared %d days through %s for %d categories.",
    len(all_dates),
    latest_date.date(),
    len(KNOWN_CATEGORIES),
)


# ## 5. Reconstruct features and run inference
#
#
#
# Append the incoming day and calculate calendar, lag, and rolling features exactly as in training. Align the encoded columns to the stored model contract before predicting.

# In[6]:


forecast_date = latest_date + pd.Timedelta(days=1)

future_rows = pd.DataFrame(
    {
        DATE_COLUMN: forecast_date,
        CATEGORY_COLUMN: KNOWN_CATEGORIES,
        TARGET_COLUMN: 0.0,
    }
)

history_and_future = pd.concat([daily_sales, future_rows], ignore_index=True)

future_features = create_time_features(history_and_future)

future_features = future_features.loc[
    future_features[DATE_COLUMN] == forecast_date
].copy()


feature_columns = artifacts["raw_feature_columns"]

X_future = pd.get_dummies(
    future_features[feature_columns], columns=[CATEGORY_COLUMN], dtype=int
)

X_future = X_future.reindex(columns=MODEL_COLUMNS, fill_value=0)

if X_future.isna().any().any():
    raise ValueError(
        "Recent sales did not provide enough history to calculate every model feature."
    )


predicted_quantities = np.rint(np.clip(model.predict(X_future), 0, None)).astype(int)

forecast = future_features[[DATE_COLUMN, CATEGORY_COLUMN]].copy()

forecast["Predicted_Qty"] = predicted_quantities

forecast = forecast.sort_values(CATEGORY_COLUMN).reset_index(drop=True)

log.info(forecast)

log.info("Forecast total units: %d", forecast["Predicted_Qty"].sum())


# ## 6. Return predictions to the result endpoint
#
#
#
# Serialize the forecast as JSON and POST it in real mode. Simulation mode displays the request body without contacting an external service.

# In[7]:


# TODO: pydantic validation
result_payload = {
    "forecast_date": forecast_date.strftime("%Y-%m-%d"),
    "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
    "predictions": [
        {
            "category": row[CATEGORY_COLUMN],
            "predicted_quantity": int(row["Predicted_Qty"]),
        }
        for _, row in forecast.iterrows()
    ],
}


sales_gateway.upload_inference_results(result_payload)


forecast[[CATEGORY_COLUMN, "Predicted_Qty"]].to_csv(
    CONFIG.output_dir / "inference_next_day_forecast.csv", index=False
)
