"""NLDAS dataset constants (no IO, no third-party imports).

One job: the products, profile and per-variable source/unit mapping shared by the Silver and
Gold layers, so planning can read them without importing xarray/netCDF4.
"""

from __future__ import annotations

PRODUCTS = ("FORA", "NOAH")
PROFILE = "legacy"

VARIABLES = {
    "FORA": {"apcp": ("Rainf", "kg m-2"), "pevap": ("PotEvap", "kg m-2")},
    "NOAH": {
        "evp": ("Evap", "kg m-2"),
        "pevpr": ("PotEvap", "W m-2"),
        "soilm": ("SoilM_0_10cm", "kg m-2"),
        "ssrun": ("Qs", "kg m-2"),
        "tsoil": ("SoilT_0_10cm", "K"),
        "lai": ("LAI", "unitless"),
        "snod": ("SnowDepth", "m"),
        "snom": ("Qsm", "kg m-2"),
        "snowc": ("SnowFrac", "fraction"),
        "weasd": ("SWE", "kg m-2"),
    },
}
