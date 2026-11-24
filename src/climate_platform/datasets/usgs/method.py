"""USGS method constants.

One job: the frozen method identity (baseline, window/rank/donor rules) that
every Silver/Weekly/Gold manifest records and verifies against.
"""

from __future__ import annotations

METHOD = {
    "baseline_start": "2020-01-01",
    "baseline_end": "2022-12-31",
    "min_days": {"7": 4, "14": 8, "28": 15},
    "week_day": "Tuesday",
    "window": "[t-window,t-1]; full calendar window required",
    "rank": "first of 1/2 ties; ceil(m/2)th of >=3 ties, 1-based",
    "station_grid": "minimum L1 decimal degrees; first original grid row breaks ties",
    "idw": "1/Euclidean decimal degrees; mean of zero-distance donors if any",
    "donors": "all valid station percentiles in HUC, no 20-donor cap or spatial window",
    "purpose": "retrospective analysis; not forecast validation",
}
WINDOWS = (7, 14, 28)
