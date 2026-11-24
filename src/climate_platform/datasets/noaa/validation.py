"""NOAA temporal/domain validation.

One job: reject Bronze/Silver tables that are empty, have missing/duplicate/irregular
dates, non-finite values, or NOAA missing-value sentinels. Shared by Silver and Gold so the
continuity contract is defined once.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def validate_table(frame: pd.DataFrame, date_column: str, frequency: str) -> pd.DataFrame:
    """Reject empty, missing-date, duplicate, gapped, non-finite, or sentinel-valued inputs."""
    if frame.empty or frame[date_column].isna().any():
        raise ValueError(f"Empty table or invalid dates: {date_column}")
    if frame[date_column].duplicated().any():
        raise ValueError(f"Duplicate dates: {date_column}")

    frame = frame.sort_values(date_column).reset_index(drop=True)
    frame[date_column] = pd.to_datetime(frame[date_column]).astype("datetime64[ns]")

    expected = pd.date_range(
        frame[date_column].min(),
        frame[date_column].max(),
        freq=frequency,
    ).astype("datetime64[ns]")
    if not pd.DatetimeIndex(frame[date_column]).equals(expected):
        raise ValueError(f"Missing or irregular dates: {date_column}")

    values = frame.drop(columns=date_column).to_numpy(dtype=float)
    if not np.isfinite(values).all() or (np.abs(values) >= 99).any():
        raise ValueError(
            "Missing/non-finite values or possible NOAA missing-value sentinels (|x| >= 99)"
        )
    return frame
