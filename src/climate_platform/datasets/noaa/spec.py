"""NOAA/CPC teleconnection dataset constants (no IO, no third-party imports).

One job: the file names, layouts and parsing widths shared by the Silver and Gold layers
and by planning. Keeping them here lets the pipeline plan from cheap constants without
importing pandas/numpy.
"""

from __future__ import annotations

import re

# AO/NAO/PNA daily CSV sources and the ENSO fixed-width source kept in Bronze.
DAILY_SPECS = [
    ("ao", "norm.daily.ao.cdas.z1000.19500101_current.csv"),
    ("nao", "norm.daily.nao.cdas.z500.19500101_current.csv"),
    ("pna", "norm.daily.pna.cdas.z500.19500101_current.csv"),
]
ENSO_FILENAME = "wksst9120.for"
REQUIRED_BRONZE_FILES = [name for _, name in DAILY_SPECS] + [ENSO_FILENAME]

SILVER_OUTPUTS = ("climate_daily.parquet", "enso_weekly.parquet")
GOLD_OUTPUTS = ("climate_weekly.parquet", "climate_weekly.csv")
# Completion marker written last, per layer root. Its presence + recorded output sizes is
# what "already done" means; bare file existence is never trusted.
COMPLETE_MARKER = "_complete.json"

MONTHS = {
    name: idx
    for idx, name in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)
}
# Glued negative SSTA pattern for 3-column sliced Nino 3.4 .for (e.g. ' 14DEC2022       25.7-0.9')
ENSO_NINO34_PATTERN = re.compile(
    r"\s*(\d{2})([A-Z]{3})(\d{4})\s+([+-]?\d+\.\d+)\s*([+-]?\d+\.\d+)\s*"
)
# Full raw NOAA wksst9120.for fixed widths (9 columns: week, 4 regions x (SST, SSTA))
ENSO_FULL_WIDTHS = [12, 7, 4, 9, 4, 9, 4, 9, 4]
