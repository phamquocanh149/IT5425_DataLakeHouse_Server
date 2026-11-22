#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
USDM Bronze to Silver Geospatial Pipeline
=========================================
Ingests raw Bronze shapefiles from USDM GIS portal, performs geospatial cleaning
(topology repair, CRS conformance, schema standardization, lineage enrichment),
and writes enterprise-grade GeoParquet partitions for the Silver Layer.

Architecture:
    Bronze: Raw shapefiles (USDM_YYYYMMDD_M.zip / unzipped shp)
    Silver: Cleaned, Validated & Standardized GeoParquet (Partitioned by week_date)
    Gold  : ML-ready Gridded CSV (usdmfinal.csv)

Author: Senior Geospatial Data Engineer
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import geopandas as gpd
import pandas as pd
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.validation import make_valid

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("USDM_Silver_Pipeline")


DM_NAME_MAP: Dict[int, str] = {
    0: "Abnormally Dry",
    1: "Moderate Drought",
    2: "Severe Drought",
    3: "Extreme Drought",
    4: "Exceptional Drought",
}

TARGET_CRS: str = "EPSG:4326"


@dataclass
class PipelineConfig:
    bronze_root: Path
    silver_root: Path
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    overwrite: bool = False
    target_crs: str = TARGET_CRS


@dataclass
class QualityMetric:
    week_date: str
    time_id: str
    source_file: str
    raw_feature_count: int = 0
    silver_feature_count: int = 0
    dm_values_present: List[int] = field(default_factory=list)
    repaired_geometries_count: int = 0
    quarantined_features_count: int = 0
    is_crs_conformed: bool = True
    status: str = "PENDING"
    notes: List[str] = field(default_factory=list)


class GeometryCleaner:
    """Handles geometry validation, topology repair, and polygon normalization."""

    @staticmethod
    def clean_geometry(geom: Any) -> Tuple[Optional[Any], bool]:
        """
        Validates and repairs a geometry using Shapely make_valid.
        Ensures output contains only Polygon or MultiPolygon components.

        Returns:
            Tuple[Optional[Geometry], bool]: (Cleaned geometry, True if repaired)
        """
        if geom is None or geom.is_empty:
            return None, False

        was_repaired = False
        if not geom.is_valid:
            try:
                geom = make_valid(geom)
                was_repaired = True
            except Exception as e:
                logger.warning(f"make_valid failed on geometry: {e}")
                return None, False

        # If it's a GeometryCollection, extract only polygonal elements
        if isinstance(geom, GeometryCollection):
            polygons = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon))]
            if not polygons:
                return None, True
            if len(polygons) == 1 and isinstance(polygons[0], Polygon):
                geom = polygons[0]
            else:
                flat_polys = []
                for p in polygons:
                    if isinstance(p, Polygon):
                        flat_polys.append(p)
                    elif isinstance(p, MultiPolygon):
                        flat_polys.extend(p.geoms)
                geom = MultiPolygon(flat_polys)
            was_repaired = True

        if geom.is_empty or geom.area <= 0:
            return None, True

        return geom, was_repaired


class USDMBronzeToSilverPipeline:
    """Orchestrates Bronze Ingestion -> Spatial Cleaning -> Silver GeoParquet Storage."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.drought_polygons_dir = self.config.silver_root / "drought_polygons"
        self.metadata_dir = self.config.silver_root / "metadata"
        self.quality_reports_dir = self.config.silver_root / "quality_reports"
        self.manifests_dir = self.config.silver_root / "manifests"

        self._init_directories()

    def _init_directories(self) -> None:
        """Create standard Silver Layer directory structure."""
        for d in [
            self.drought_polygons_dir,
            self.metadata_dir,
            self.quality_reports_dir,
            self.manifests_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def discover_bronze_files(self) -> List[Tuple[str, str, Path]]:
        """
        Scans bronze_root for USDM shapefiles or zip packages.
        Returns:
            List[Tuple[week_date_iso, time_id, path_to_shp_or_zip]]
        """
        shp_dir = self.config.bronze_root / "shp"
        if not shp_dir.exists():
            shp_dir = self.config.bronze_root

        logger.info(f"Scanning for Bronze files in: {shp_dir}")
        found_items: Dict[str, Path] = {}

        # 1. Search for uncompressed .shp files first (preferred)
        for shp_file in sorted(shp_dir.glob("**/USDM_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].shp")):
            match = re.search(r"USDM_(\d{8})", shp_file.name)
            if match:
                time_id = match.group(1)
                found_items[time_id] = shp_file

        # 2. Search for .zip files as fallback
        for zip_file in sorted(shp_dir.glob("**/USDM_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_M.zip")):
            match = re.search(r"USDM_(\d{8})_M\.zip", zip_file.name)
            if match:
                time_id = match.group(1)
                if time_id not in found_items:
                    found_items[time_id] = zip_file

        # Filter by start_date and end_date
        results: List[Tuple[str, str, Path]] = []
        for time_id in sorted(found_items.keys()):
            if self.config.start_date and time_id < self.config.start_date.replace("-", ""):
                continue
            if self.config.end_date and time_id > self.config.end_date.replace("-", ""):
                continue

            try:
                dt = datetime.datetime.strptime(time_id, "%Y%m%d").date()
                week_date_iso = dt.strftime("%Y-%m-%d")
                results.append((week_date_iso, time_id, found_items[time_id]))
            except ValueError:
                logger.warning(f"Invalid date in filename: {time_id}")

        logger.info(f"Discovered {len(results)} valid weekly packages within target window.")
        return results

    def read_bronze_feature_data(self, file_path: Path) -> gpd.GeoDataFrame:
        """Reads raw shapefile (directly or via zip) into GeoDataFrame."""
        if file_path.suffix.lower() == ".zip":
            # Pyogrio / Fiona supports reading directly from zip
            zip_uri = f"zip://{file_path.resolve()}"
            gdf = gpd.read_file(zip_uri)
        else:
            gdf = gpd.read_file(file_path)
        return gdf

    def process_week(
        self, week_date_iso: str, time_id: str, file_path: Path
    ) -> Tuple[Optional[gpd.GeoDataFrame], QualityMetric]:
        """
        Performs data cleaning, standardization, and quality gating for one week.
        """
        metric = QualityMetric(
            week_date=week_date_iso,
            time_id=time_id,
            source_file=file_path.name,
        )

        partition_path = (
            self.drought_polygons_dir
            / f"week_date={week_date_iso}"
            / "data.parquet"
        )

        if partition_path.exists() and not self.config.overwrite:
            logger.info(f"[{time_id}] Partition already exists. Skipping (overwrite=False).")
            metric.status = "SKIPPED_EXISTING"
            return None, metric

        try:
            raw_gdf = self.read_bronze_feature_data(file_path)
        except Exception as e:
            logger.error(f"[{time_id}] CRITICAL: Failed to read Bronze file {file_path}: {e}")
            metric.status = "CRITICAL_ERROR"
            metric.notes.append(f"File read failed: {str(e)}")
            return None, metric

        metric.raw_feature_count = len(raw_gdf)

        # 1. Schema Validation
        required_cols = {"DM", "geometry"}
        if not required_cols.issubset(raw_gdf.columns):
            msg = f"Missing required columns. Found: {list(raw_gdf.columns)}"
            logger.error(f"[{time_id}] CRITICAL: {msg}")
            metric.status = "CRITICAL_ERROR"
            metric.notes.append(msg)
            return None, metric

        # 2. CRS Validation & Conformance
        if raw_gdf.crs is None:
            logger.warning(f"[{time_id}] Warning: CRS missing in source. Assigning EPSG:4326.")
            raw_gdf = raw_gdf.set_crs(TARGET_CRS)
            metric.is_crs_conformed = False
            metric.notes.append("Source CRS was None; explicitly set to EPSG:4326.")
        elif str(raw_gdf.crs).upper() != TARGET_CRS:
            raw_gdf = raw_gdf.to_crs(TARGET_CRS)
            metric.notes.append(f"Reprojected from {raw_gdf.crs} to {TARGET_CRS}.")

        # 3. Feature cleaning and filtering
        cleaned_records: List[Dict[str, Any]] = []
        quarantined = 0
        repaired = 0

        now_utc = pd.Timestamp.now(datetime.timezone.utc)

        for idx, row in raw_gdf.iterrows():
            dm = row.get("DM")

            # Domain check: DM must be in [0, 4]
            try:
                dm_val = int(dm)
                if dm_val not in (0, 1, 2, 3, 4):
                    logger.warning(f"[{time_id}] Invalid DM value: {dm}. Quarantining feature.")
                    quarantined += 1
                    continue
            except (TypeError, ValueError):
                logger.warning(f"[{time_id}] Non-integer DM value: {dm}. Quarantining.")
                quarantined += 1
                continue

            raw_geom = row.geometry
            clean_geom, was_repaired = GeometryCleaner.clean_geometry(raw_geom)

            if clean_geom is None or clean_geom.is_empty:
                logger.warning(f"[{time_id}] Empty/Invalid geometry after repair. Quarantining.")
                quarantined += 1
                continue

            if was_repaired:
                repaired += 1

            source_obj_id = int(row.get("OBJECTID", idx))
            shape_leng = float(row.get("Shape_Leng", 0.0)) if pd.notnull(row.get("Shape_Leng")) else None
            shape_area = float(row.get("Shape_Area", 0.0)) if pd.notnull(row.get("Shape_Area")) else None

            cleaned_records.append({
                "week_date": week_date_iso,
                "time_id": time_id,
                "dm_value": dm_val,
                "drought_category": f"D{dm_val}",
                "drought_name": DM_NAME_MAP[dm_val],
                "shape_length": shape_leng,
                "shape_area": shape_area,
                "geometry": clean_geom,
                "source_file": file_path.name,
                "source_object_id": source_obj_id,
                "is_geom_repaired": was_repaired,
                "processed_at": now_utc,
            })

        metric.repaired_geometries_count = repaired
        metric.quarantined_features_count = quarantined
        metric.silver_feature_count = len(cleaned_records)
        metric.dm_values_present = sorted([r["dm_value"] for r in cleaned_records])

        if len(cleaned_records) == 0:
            logger.error(f"[{time_id}] CRITICAL: All features quarantined. Zero output records.")
            metric.status = "CRITICAL_ERROR"
            metric.notes.append("Zero valid records after geospatial cleaning.")
            return None, metric

        silver_gdf = gpd.GeoDataFrame(cleaned_records, geometry="geometry", crs=TARGET_CRS)

        # Enforce column types
        silver_gdf["dm_value"] = silver_gdf["dm_value"].astype("int8")
        silver_gdf["source_object_id"] = silver_gdf["source_object_id"].astype("int64")

        # Save to partition
        partition_path.parent.mkdir(parents=True, exist_ok=True)
        silver_gdf.to_parquet(partition_path, compression="snappy")
        logger.info(
            f"[{time_id}] Successfully wrote Silver partition ({len(silver_gdf)} features, "
            f"{repaired} repaired, {quarantined} quarantined) -> {partition_path.parent.name}"
        )

        metric.status = "SUCCESS"
        return silver_gdf, metric

    def run(self) -> Dict[str, Any]:
        """Executes full pipeline for discovered weeks and exports reports."""
        start_time = datetime.datetime.now()
        files = self.discover_bronze_files()
        if not files:
            logger.warning("No files found to process. Exiting.")
            return {"status": "EMPTY", "processed_count": 0}

        metrics: List[QualityMetric] = []
        all_silver_gdfs: List[gpd.GeoDataFrame] = []

        for week_date_iso, time_id, file_path in files:
            silver_gdf, metric = self.process_week(week_date_iso, time_id, file_path)
            metrics.append(metric)
            if silver_gdf is not None:
                all_silver_gdfs.append(silver_gdf)

        # Export consolidated parquet dataset if records were processed
        all_data_path = self.drought_polygons_dir / "all_drought_polygons.parquet"
        if all_silver_gdfs:
            combined_gdf = pd.concat(all_silver_gdfs, ignore_index=True)
            combined_gdf = gpd.GeoDataFrame(combined_gdf, geometry="geometry", crs=TARGET_CRS)
            combined_gdf.to_parquet(all_data_path, compression="snappy")
            logger.info(f"Consolidated Silver dataset saved: {all_data_path} ({len(combined_gdf)} total features)")

        # Generate Quality Reports & Manifests
        metrics_df = pd.DataFrame([asdict(m) for m in metrics])
        quality_csv = self.quality_reports_dir / "quality_report.csv"
        quality_json = self.quality_reports_dir / "quality_report.json"
        metrics_df.to_csv(quality_csv, index=False)

        summary = {
            "execution_time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "elapsed_seconds": (datetime.datetime.now() - start_time).total_seconds(),
            "total_weeks_evaluated": len(files),
            "successful_weeks": int((metrics_df["status"] == "SUCCESS").sum()),
            "skipped_weeks": int((metrics_df["status"] == "SKIPPED_EXISTING").sum()),
            "failed_weeks": int((metrics_df["status"] == "CRITICAL_ERROR").sum()),
            "total_raw_features": int(metrics_df["raw_feature_count"].sum()),
            "total_silver_features": int(metrics_df["silver_feature_count"].sum()),
            "total_repaired_geometries": int(metrics_df["repaired_geometries_count"].sum()),
            "total_quarantined_features": int(metrics_df["quarantined_features_count"].sum()),
            "target_crs": TARGET_CRS,
            "bronze_root": str(self.config.bronze_root),
            "silver_root": str(self.config.silver_root),
        }

        with open(quality_json, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "metrics": [asdict(m) for m in metrics]}, f, indent=2)

        # Generate Manifest
        manifest_data = {
            "pipeline_name": "USDM_Bronze_To_Silver",
            "pipeline_version": "1.0.0",
            "run_timestamp": summary["execution_time_utc"],
            "weeks_processed": [
                {
                    "week_date": m.week_date,
                    "time_id": m.time_id,
                    "source_file": m.source_file,
                    "silver_features": m.silver_feature_count,
                    "status": m.status,
                }
                for m in metrics
            ],
        }
        manifest_json = self.manifests_dir / "manifest.json"
        with open(manifest_json, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        logger.info("=" * 60)
        logger.info(f"PIPELINE COMPLETED: {summary['successful_weeks']}/{summary['total_weeks_evaluated']} weeks processed.")
        logger.info(f"Total Silver Features: {summary['total_silver_features']}")
        logger.info(f"Repaired Geometries: {summary['total_repaired_geometries']}")
        logger.info(f"Quality Report: {quality_json}")
        logger.info("=" * 60)

        return summary


def parse_arguments() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    # repo_root is 2 levels up from silver/scripts/
    repo_root = script_dir.parent.parent if (script_dir.parent.parent / "bronze").exists() else script_dir.parent
    default_bronze = repo_root / "bronze" / "data"
    default_silver = repo_root / "silver" / "data"

    parser = argparse.ArgumentParser(
        description="USDM Bronze to Silver Geospatial Medallion Pipeline."
    )
    parser.add_argument(
        "--bronze-root",
        type=Path,
        default=default_bronze,
        help="Path to Bronze root containing shp directory.",
    )
    parser.add_argument(
        "--silver-root",
        type=Path,
        default=default_silver,
        help="Path to output Silver layer.",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2020-01-07",
        help="Start date filter (YYYY-MM-DD or YYYYMMDD).",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="2022-06-28",
        help="End date filter (YYYY-MM-DD or YYYYMMDD).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing Silver partitions if present.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    logger.setLevel(getattr(logging, args.log_level))

    config = PipelineConfig(
        bronze_root=args.bronze_root,
        silver_root=args.silver_root,
        start_date=args.start_date,
        end_date=args.end_date,
        overwrite=args.overwrite,
    )

    runner = USDMBronzeToSilverPipeline(config)
    runner.run()


if __name__ == "__main__":
    main()



