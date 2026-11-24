"""NLDAS Bronze -> Silver science.

One job: aggregate each Bronze hour. Weekly: ``apcp`` summed, other variables ``sum / 168``;
4x4 blocks reduced latitude then longitude; a block with >0.7 missing becomes null. Writes
Silver Parquet partitions plus the source manifest. No orchestration, no lock.
"""

from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path

from climate_platform.datasets.nldas import bronze, references, spec
from climate_platform.datasets.nldas.deps import require
from climate_platform.datasets.nldas.partition import write_partition
from climate_platform.medallion.io import file_hash, write_text_atomic

SILVER_INCOMPATIBLE = (
    "profile",
    "version",
    "grid_reference_sha256",
    "calendar_reference_sha256",
    "r25_policy",
)


def aggregate_blocks(values, precipitation=False):
    """Reduce 4x4 blocks; latitude is averaged before longitude."""
    import numpy as np

    missing = np.isnan(values).mean(axis=(1, 3))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if precipitation:
            result = np.nansum(np.nansum(values, axis=1), axis=2)
        else:
            result = np.nanmean(np.nanmean(values, axis=1), axis=2)
    result[missing > 0.7] = np.nan
    return result, 1 - missing


def load_references(grid_path, calendar_path):
    import pandas as pd

    coords = references.load_references_grid(grid_path)
    calendar = pd.read_csv(calendar_path, dtype=str)
    if list(calendar.columns) != ["week_date"] or calendar.empty:
        raise ValueError("Expected nonempty week_date reference calendar")
    dates = pd.DatetimeIndex(pd.to_datetime(calendar.week_date, format="%Y-%m-%d", errors="raise"))
    if dates.isna().any() or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("Calendar must contain unique dates in increasing order")
    if any(dates.dayofweek != 1) or not dates.equals(dates.normalize()):
        raise ValueError("Reference dates must be Tuesdays at midnight")
    return coords.reset_index(drop=True), dates


def read_hour(path, product, timestamp, grid):
    import netCDF4
    import numpy as np
    import pandas as pd
    import xarray as xr

    variables = spec.VARIABLES[product]
    result = {}
    coverage = {}
    # Native netCDF Windows builds may reject Vietnamese paths. Python reads the
    # single file into memory; netCDF sees only an ASCII logical filename.
    handle = netCDF4.Dataset("hour.nc", memory=path.read_bytes())
    with xr.open_dataset(
        xr.backends.NetCDF4DataStore(handle), decode_cf=True, mask_and_scale=True
    ) as ds:
        if ds.sizes.get("time") != 1:
            raise ValueError(f"Expected one hourly record: {path}")
        actual = pd.Timestamp(ds.time.values[0])
        if actual != timestamp:
            raise ValueError(f"Time coordinate disagrees with filename: {path}")
        ds = ds.sortby("lat").sortby("lon")
        # Align blocks by known grid boundaries, never by array row number.
        ds = ds.sel(lat=slice(25, 50), lon=slice(-125, -65))
        lat = ds.lat.values
        lon = ds.lon.values
        if len(lat) % 4 or len(lon) % 4:
            raise ValueError("Input extent is not aligned to complete 4x4 blocks")
        if not (np.allclose(np.diff(lat), 0.125) and np.allclose(np.diff(lon), 0.125)):
            raise ValueError("Expected regular 0.125-degree input")
        if not (np.isclose(lat[0], 25.0625) and np.isclose(lon[0], -124.9375)):
            raise ValueError("Input origin differs from NLDAS grid")
        centers_y = lat.reshape(-1, 4).mean(axis=1)
        centers_x = lon.reshape(-1, 4).mean(axis=1)
        iy = np.rint((grid.lat.to_numpy() - centers_y[0]) / 0.5).astype(int)
        ix = np.rint((grid.lon.to_numpy() - centers_x[0]) / 0.5).astype(int)
        inside = (iy >= 0) & (iy < len(centers_y)) & (ix >= 0) & (ix < len(centers_x))
        if not (
            np.allclose(centers_y[iy[inside]], grid.lat.to_numpy()[inside])
            and np.allclose(centers_x[ix[inside]], grid.lon.to_numpy()[inside])
        ):
            raise ValueError("Reference centers do not align with NLDAS blocks")
        for output, (source, unit) in variables.items():
            if source not in ds:
                raise ValueError(f"Missing variable {source}: {path}")
            da = ds[source]
            if da.attrs.get("units") != unit:
                raise ValueError(f"Unexpected units for {source}: {da.attrs.get('units')}")
            if set(da.dims) != {"time", "lat", "lon"}:
                raise ValueError(f"Unexpected dimensions for {source}: {da.dims}")
            values = da.isel(time=0).transpose("lat", "lon").values.astype("float64")
            values[~np.isfinite(values) | (values == -9999)] = np.nan
            blocks = values.reshape(len(lat) // 4, 4, len(lon) // 4, 4)
            reduced, fraction = aggregate_blocks(blocks, output == "apcp")
            v = np.full(len(grid), np.nan)
            c = np.full(len(grid), np.nan)
            v[inside] = reduced[iy[inside], ix[inside]]
            c[inside] = fraction[iy[inside], ix[inside]]
            result[output] = v
            coverage[output] = c
        version = ds.attrs.get("version", "unknown")
    return result, coverage, version


def build_metadata(product, grid_path, calendar_path):
    return {
        "product": product,
        "profile": spec.PROFILE,
        "version": "1.0",
        "grid_reference_sha256": file_hash(grid_path),
        "calendar_reference_sha256": file_hash(calendar_path),
        "units": {name: unit for name, (_, unit) in spec.VARIABLES[product].items()},
        "time_rule": ("Timestamp convention: [Tuesday-7d 00:00, Tuesday 00:00); no hour shift."),
        "spatial_rule": (
            "APCP sum; others nested mean latitude then longitude; mask if missing fraction > 0.7."
        ),
        "temporal_rule": (
            "APCP sum; others sum / 168; any invalid hour gives null for that variable."
        ),
        "land_fraction_policy": (
            "Threshold 70% land (also 11 of 16); missing fraction > 0.7 is rejected."
        ),
        "r25_policy": "keep",
        "variables": spec.VARIABLES[product],
    }


def build_silver(
    product,
    *,
    bronze_root,
    references_dir,
    silver_output,
    start=None,
    end=None,
    weeks=None,
    log=print,
):
    """Build Silver Parquet for ``product`` from Bronze NetCDF files."""
    if product not in spec.VARIABLES:
        raise ValueError(f"Unknown product: {product}")
    require(["numpy", "pandas", "pyarrow", "xarray", "netCDF4"], "NLDAS Silver")
    import numpy as np
    import pandas as pd

    references_dir = Path(references_dir)
    grid_path = references_dir / "grid_reference.parquet"
    calendar_path = references_dir / "week_dates.csv"
    grid, dates = load_references(grid_path, calendar_path)
    if start:
        dates = dates[dates >= pd.Timestamp(start)]
    if end:
        dates = dates[dates <= pd.Timestamp(end)]
    if weeks is not None:
        requested = pd.DatetimeIndex(sorted({pd.Timestamp(day) for day in weeks}))
        unknown = requested.difference(dates)
        if len(unknown):
            raise ValueError(f"Requested weeks are outside the reference calendar: {unknown}")
        dates = dates[dates.isin(requested)]
    metadata = build_metadata(product, grid_path, calendar_path)

    records = bronze.inventory(bronze_root, product)
    if not records:
        raise ValueError(f"No {product} files found under {bronze_root}")
    inputs = {pd.Timestamp(stamp): path for stamp, path in records.items()}
    dates = dates[(dates > min(inputs)) & (dates - pd.Timedelta(days=7) <= max(inputs))]
    if dates.empty:
        raise ValueError("No input data overlaps the selected reference weeks")

    rows = []
    manifest = []
    for week_date in dates:
        hours = pd.date_range(week_date - pd.Timedelta(days=7), periods=168, freq="h")
        sums = {name: np.zeros(len(grid)) for name in spec.VARIABLES[product]}
        counts = {name: np.zeros(len(grid), dtype=np.int16) for name in sums}
        fractions = {name: np.full(len(grid), np.nan) for name in sums}
        available = [hour for hour in hours if hour in inputs]
        for hour in available:
            path = inputs[hour]
            data, coverage, version = read_hour(path, product, hour, grid)
            manifest.append(
                {
                    "timestamp": hour.isoformat(),
                    "path": str(path.resolve()),
                    "sha256": file_hash(path),
                    "source_version": str(version),
                }
            )
            for name in sums:
                valid = np.isfinite(data[name])
                sums[name] += np.where(valid, data[name], 0)
                counts[name] += valid
                fractions[name] = np.fmin(fractions[name], coverage[name])
        chunk = grid.copy()
        chunk["week_date"] = week_date
        chunk["window_start"] = hours[0]
        chunk["window_end"] = week_date
        chunk["n_source_hours"] = len(available)
        for name in sums:
            chunk[name] = np.where(
                counts[name] == 168,
                sums[name] if name == "apcp" else sums[name] / 168,
                np.nan,
            )
            chunk[f"{name}_valid_hours"] = counts[name]
            chunk[f"{name}_min_valid_pixel_fraction"] = fractions[name]
        chunk["quality_status"] = np.where(
            len(available) < 168,
            "incomplete_week",
            np.where(chunk[list(sums)].notna().all(axis=1), "complete", "masked_or_missing"),
        )
        chunk["processing_version"] = "1.0"
        chunk["aggregation_profile"] = spec.PROFILE
        rows.append(chunk)
        log(f"{product} {week_date.date()}: {len(available)}/168 input hours")
    if not rows:
        raise ValueError("No input data overlaps the selected reference weeks")
    frame = pd.concat(rows, ignore_index=True)
    manifest_text = json.dumps(manifest, indent=2)
    manifest_id = hashlib.sha256(manifest_text.encode()).hexdigest()
    frame["source_manifest_id"] = manifest_id
    output = Path(silver_output)
    output.mkdir(parents=True, exist_ok=True)
    write_text_atomic(output / f"manifest_{manifest_id}.json", manifest_text)
    write_partition(frame, output, metadata, SILVER_INCOMPATIBLE)
    log(f"Wrote {len(frame)} rows to {output}")
    return {
        "product": product,
        "weeks": [week_date.date().isoformat() for week_date in dates],
        "rows": len(frame),
        "output": str(output),
        "manifest_id": manifest_id,
    }
