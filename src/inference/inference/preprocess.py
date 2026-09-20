import pandas as pd


def payload_to_dataframe(source_payload: dict) -> pd.DataFrame:
    if isinstance(
        source_payload, list
    ):  # TODO: validate - is this code path even alive?
        source_records = source_payload

    elif isinstance(source_payload, dict):
        source_records = source_payload.get("records", source_payload.get("data"))

    else:
        source_records = None

    if not isinstance(source_records, list) or not source_records:
        raise ValueError(
            "The recent-sales endpoint must return a non-empty JSON record list."
        )

    return pd.DataFrame.from_records(source_records)
