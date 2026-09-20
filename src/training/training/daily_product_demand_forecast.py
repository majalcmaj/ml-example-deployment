# # Next-day product demand forecast
#
#
#
# This notebook uses pandas to clean daily coffee-shop sales and trains one global XGBoost model to predict how many units of each menu category will be sold on the day after the latest observation.
#
#
#
# The workflow uses a chronological validation period, calculates outlier limits only from earlier training data, and builds lag features only from past sales.

# ## 1. Install and import dependencies
#
#
#
# The cell installs only missing packages, then imports the libraries used below.

# In[1]:


import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from common.consts import CATEGORY_COLUMN, DATE_COLUMN, TARGET_COLUMN
from common.logger import get_logger
from common.preprocessing import (
    aggregate_per_category,
    columns_to_expected_types,
    get_valid_date_target_array,
    validate_required_columns_present,
)
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

from training.config import CONFIG

log = get_logger(__name__)

RANDOM_SEED = 42

pd.set_option("display.max_rows", 100)

pd.set_option("display.max_columns", 50)


# ## 2. Load CSV files
#
#
#
# Find the project data directory, load every CSV with pandas, label its source, and combine all rows.

# In[2]:


DATA_DIR = CONFIG.data_dir

csv_files = sorted(DATA_DIR.glob("*.csv"))
if not csv_files:
    raise FileNotFoundError(f"No CSV files found in {DATA_DIR}")


frames = []
for csv_file in csv_files:
    frame = pd.read_csv(csv_file)
    frame["Source_File"] = csv_file.name
    frames.append(frame)


raw_sales = pd.concat(frames, ignore_index=True)

log.info(f"Loaded {len(raw_sales):,} rows from {len(csv_files)} file(s):")

log.info([path.name for path in csv_files])


# ## 3. Inspect and validate the data
#
#
#
# Review the data before changing it. The three configuration values below identify the date, product category, and quantity columns.

# In[3]:


VALIDATION_DAYS = 30


log.info(raw_sales.head())

log.info("Shape: %s", raw_sales.shape)

log.info("Columns: %s", raw_sales.columns.tolist())

log.info(raw_sales.dtypes.rename("dtype").to_frame())

log.info(raw_sales.isna().sum().rename("missing_values").to_frame())

log.info("Exact duplicate rows: %s", raw_sales.duplicated().sum())

log.info(raw_sales.describe(include="all").transpose())


# ## 4. Clean and preprocess sales data
#
#
#
# Parse dates and quantities, standardize category labels, and remove invalid records. Missing or negative quantities cannot represent usable demand and are removed. Repeated date-category rows are valid observations and will be summed in the next section.

# In[4]:

validate_required_columns_present(raw_sales)
sales = raw_sales.copy()

unnamed_columns = [
    column for column in sales.columns if column.lower().startswith("unnamed:")
]
sales = sales.drop(columns=unnamed_columns)
sales = columns_to_expected_types(sales)

rows_before = len(sales)

sales = sales.drop_duplicates()
valid_rows = get_valid_date_target_array(sales)
valid_rows &= sales[CATEGORY_COLUMN].notna() & sales[CATEGORY_COLUMN].ne("")

sales = sales.loc[valid_rows].copy()

log.info(f"Removed {rows_before - len(sales):,} exact duplicate or invalid rows.")
log.info(
    f"Clean date range: {sales[DATE_COLUMN].min().date()} to {sales[DATE_COLUMN].max().date()}"
)
log.info(f"Product categories: {sales[CATEGORY_COLUMN].nunique()}")


# ## 5. Aggregate daily sales by category
#
#
#
# Sum repeated rows for each day and product. Then create every date-product combination; when a product is absent on a day, interpret it as zero units sold.

# In[5]:


daily_sales = (
    sales.groupby([DATE_COLUMN, CATEGORY_COLUMN], as_index=False)[TARGET_COLUMN]
    .sum()
    .sort_values([CATEGORY_COLUMN, DATE_COLUMN])
)

all_categories = sorted(daily_sales[CATEGORY_COLUMN].unique())
all_dates = pd.date_range(
    daily_sales[DATE_COLUMN].min(), daily_sales[DATE_COLUMN].max(), freq="D"
)


complete_index = pd.MultiIndex.from_product(
    [all_dates, all_categories], names=[DATE_COLUMN, CATEGORY_COLUMN]
)

daily_sales = aggregate_per_category(complete_index, daily_sales)

log.info(
    f"Complete panel: {len(all_dates)} days x {len(all_categories)} categories = {len(daily_sales):,} rows"
)

log.info(daily_sales.head())


# ## 6. Remove sales outliers
#
#
#
# Use the 1.5 x IQR rule separately for each product. Bounds are calculated only from dates before validation, preventing future validation data from influencing training cleanup. Outlier target rows are excluded from model fitting; the untouched validation period remains suitable for honest evaluation.

# In[6]:


validation_start = daily_sales[DATE_COLUMN].max() - pd.Timedelta(
    days=VALIDATION_DAYS - 1
)

bounds_source = daily_sales.loc[daily_sales[DATE_COLUMN] < validation_start]

category_quartiles = (
    bounds_source.groupby(CATEGORY_COLUMN)[TARGET_COLUMN]
    .quantile([0.25, 0.75])
    .unstack()
)

category_quartiles.columns = ["Q1", "Q3"]

category_quartiles["IQR"] = category_quartiles["Q3"] - category_quartiles["Q1"]

category_quartiles["Lower_Bound"] = (
    category_quartiles["Q1"] - 1.5 * category_quartiles["IQR"]
).clip(lower=0)

category_quartiles["Upper_Bound"] = (
    category_quartiles["Q3"] + 1.5 * category_quartiles["IQR"]
)


daily_sales = daily_sales.join(
    category_quartiles[["Lower_Bound", "Upper_Bound"]], on=CATEGORY_COLUMN
)

daily_sales["Is_Outlier"] = (
    daily_sales[DATE_COLUMN] < validation_start
) & ~daily_sales[TARGET_COLUMN].between(
    daily_sales["Lower_Bound"], daily_sales["Upper_Bound"]
)

log.info(f"Training outliers marked for removal: {daily_sales['Is_Outlier'].sum():,}")

log.info(category_quartiles.head())


plot_category = daily_sales.groupby(CATEGORY_COLUMN)["Is_Outlier"].sum().idxmax()

plot_data = daily_sales.loc[daily_sales[CATEGORY_COLUMN] == plot_category]

fig, axes = plt.subplots(1, 2, figsize=(14, 4), sharey=True)

axes[0].plot(plot_data[DATE_COLUMN], plot_data[TARGET_COLUMN], linewidth=1)

axes[0].scatter(
    plot_data.loc[plot_data["Is_Outlier"], DATE_COLUMN],
    plot_data.loc[plot_data["Is_Outlier"], TARGET_COLUMN],
    color="crimson",
    label="Removed from training",
)

axes[0].set_title(f"Before removal: {plot_category}")

axes[0].legend()

clean_plot_data = plot_data.loc[~plot_data["Is_Outlier"]]

axes[1].plot(
    clean_plot_data[DATE_COLUMN],
    clean_plot_data[TARGET_COLUMN],
    linewidth=1,
    color="seagreen",
)

axes[1].set_title("Training data after removal")

for axis in axes:
    axis.set_xlabel("Date")

    axis.set_ylabel("Units sold")

plt.tight_layout()

plt.show()


# ## 7. Create time-series features
#
#
#
# Add calendar fields plus category-specific lags and rolling averages. Every sales feature is shifted first, so it contains only information available before the forecast date.

# In[7]:


from common.features import create_time_features

featured_sales = create_time_features(daily_sales)

history_features = [
    column
    for column in featured_sales.columns
    if column.startswith(("Lag_", "Rolling_"))
]

featured_sales = featured_sales.dropna(subset=history_features).reset_index(drop=True)

log.info(f"Rows available after 28 days of feature history: {len(featured_sales):,}")

log.info(featured_sales.head())


# ## 8. Create a chronological train-validation split
#
#
#
# Use all clean observations before the final 30 days for training. Random splitting would let future behavior leak into the training set and would overstate forecasting accuracy.

# In[8]:


feature_columns = [
    CATEGORY_COLUMN,
    "Day_Of_Week",
    "Month",
    "Day_Of_Month",
    "Day_Of_Year",
    "Is_Weekend",
    *history_features,
]

train_mask = (featured_sales[DATE_COLUMN] < validation_start) & ~featured_sales[
    "Is_Outlier"
]

validation_mask = featured_sales[DATE_COLUMN] >= validation_start


train_data = featured_sales.loc[train_mask].copy()

validation_data = featured_sales.loc[validation_mask].copy()

X_train = pd.get_dummies(
    train_data[feature_columns], columns=[CATEGORY_COLUMN], dtype=int
)

X_validation = pd.get_dummies(
    validation_data[feature_columns], columns=[CATEGORY_COLUMN], dtype=int
)

X_validation = X_validation.reindex(columns=X_train.columns, fill_value=0)

y_train = train_data[TARGET_COLUMN]

y_validation = validation_data[TARGET_COLUMN]


log.info(
    f"Training: {train_data[DATE_COLUMN].min().date()} to {train_data[DATE_COLUMN].max().date()}, {len(train_data):,} rows"
)

log.info(
    f"Validation: {validation_data[DATE_COLUMN].min().date()} to {validation_data[DATE_COLUMN].max().date()}, {len(validation_data):,} rows"
)

log.info("Model features: %s", X_train.shape[1])


# ## 9. Train the XGBoost model
#
#
#
# Train one model across all products. The Poisson objective is designed for non-negative count-like targets, and one-hot columns allow each menu category to have its own learned effect.

# In[9]:


model = XGBRegressor(
    objective="count:poisson",
    n_estimators=400,
    learning_rate=0.05,
    max_depth=6,
    min_child_weight=3,
    subsample=0.85,
    colsample_bytree=0.85,
    reg_lambda=1.0,
    random_state=RANDOM_SEED,
    n_jobs=-1,
    eval_metric="mae",
)

model.fit(X_train, y_train, eval_set=[(X_validation, y_validation)], verbose=False)

log.info("Model training complete.")


# ## 10. Evaluate forecast accuracy
#
#
#
# Report MAE, RMSE, and WMAPE overall and by product. WMAPE is total absolute error divided by total actual demand, which makes it useful for comparing aggregate business impact.

# In[10]:


validation_predictions = np.clip(model.predict(X_validation), 0, None)

evaluation = validation_data[[DATE_COLUMN, CATEGORY_COLUMN, TARGET_COLUMN]].copy()

evaluation["Predicted_Qty"] = validation_predictions

evaluation["Absolute_Error"] = (
    evaluation[TARGET_COLUMN] - evaluation["Predicted_Qty"]
).abs()


overall_metrics = pd.Series(
    {
        "MAE": mean_absolute_error(
            evaluation[TARGET_COLUMN], evaluation["Predicted_Qty"]
        ),
        "RMSE": mean_squared_error(
            evaluation[TARGET_COLUMN], evaluation["Predicted_Qty"]
        )
        ** 0.5,
        "WMAPE_Percent": 100
        * evaluation["Absolute_Error"].sum()
        / evaluation[TARGET_COLUMN].sum(),
    },
    name="Overall",
)

log.info(overall_metrics.to_frame())


category_metrics = (
    evaluation.groupby(CATEGORY_COLUMN)
    .apply(
        lambda group: pd.Series(
            {
                "MAE": group["Absolute_Error"].mean(),
                "RMSE": np.sqrt(
                    np.mean((group[TARGET_COLUMN] - group["Predicted_Qty"]) ** 2)
                ),
                "WMAPE_Percent": 100
                * group["Absolute_Error"].sum()
                / max(group[TARGET_COLUMN].sum(), 1),
            }
        ),
        include_groups=False,
    )
    .sort_values("WMAPE_Percent")
)

log.info(category_metrics)


daily_evaluation = evaluation.groupby(DATE_COLUMN)[
    [TARGET_COLUMN, "Predicted_Qty"]
].sum()

daily_evaluation.plot(
    figsize=(13, 5), title="Validation: actual vs predicted total daily units"
)

plt.ylabel("Units sold")

plt.tight_layout()

plt.show()


# ## 11. Predict incoming-day sales by category
#
#
#
# Append one placeholder row per product for the day after the latest observed date. Feature creation reads the real history through the prior day; the placeholder target itself is never used because all demand features are shifted. Predictions are rounded to whole units.

# In[11]:


forecast_date = daily_sales[DATE_COLUMN].max() + pd.Timedelta(days=1)

future_rows = pd.DataFrame(
    {
        DATE_COLUMN: forecast_date,
        CATEGORY_COLUMN: all_categories,
        TARGET_COLUMN: 0.0,
        "Lower_Bound": np.nan,
        "Upper_Bound": np.nan,
        "Is_Outlier": False,
    }
)

history_and_future = pd.concat([daily_sales, future_rows], ignore_index=True)

future_features = create_time_features(history_and_future)

future_features = future_features.loc[
    future_features[DATE_COLUMN] == forecast_date
].copy()


X_future = pd.get_dummies(
    future_features[feature_columns], columns=[CATEGORY_COLUMN], dtype=int
)

X_future = X_future.reindex(columns=X_train.columns, fill_value=0)

future_predictions = np.clip(model.predict(X_future), 0, None)


next_day_forecast = future_features[[DATE_COLUMN, CATEGORY_COLUMN]].copy()

next_day_forecast["Predicted_Qty"] = np.rint(future_predictions).astype(int)

next_day_forecast = next_day_forecast.sort_values(
    "Predicted_Qty", ascending=False
).reset_index(drop=True)

log.info(next_day_forecast)

log.info("Predicted total units: %s", next_day_forecast["Predicted_Qty"].sum())


# ## 12. Save predictions and model artifacts
#
#
#
# Save the incoming-day forecast as CSV plus the fitted model and preprocessing metadata needed to reproduce the model inputs.

# In[12]:


OUTPUT_DIR = CONFIG.output_dir

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


prediction_path = OUTPUT_DIR / "next_day_product_forecast.csv"

model_path = OUTPUT_DIR / "xgb_daily_product_demand.json"

metadata_path = OUTPUT_DIR / "forecast_metadata.joblib"


next_day_forecast.to_csv(prediction_path, index=False)

model.save_model(model_path)

artifacts = {
    "model_feature_columns": X_train.columns.tolist(),
    "raw_feature_columns": feature_columns,
    "categories": all_categories,
    "category_dummy_columns": [
        column for column in X_train.columns if column.startswith(f"{CATEGORY_COLUMN}_")
    ],
    "configuration": {
        "date_column": DATE_COLUMN,
        "category_column": CATEGORY_COLUMN,
        "target_column": TARGET_COLUMN,
        "validation_days": VALIDATION_DAYS,
        "random_seed": RANDOM_SEED,
    },
    "outlier_bounds": category_quartiles.reset_index(),
    "validation_metrics": overall_metrics.to_dict(),
}

joblib.dump(artifacts, metadata_path)


log.info("Saved predictions: %s", prediction_path)
log.info("Saved XGBoost model: %s", model_path)
log.info("Saved metadata: %s", metadata_path)
log.info(artifacts)
