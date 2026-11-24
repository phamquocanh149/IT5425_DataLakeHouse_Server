"""Container-only synthetic fixture for the isolated Stage 5 MinIO restore drill."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    from climate_platform.config import settings
    from climate_platform.datasets.usdm.processor import DATASET_KEY, package_raw, run_pipeline
    from climate_platform.s3.minio_repository import S3Storage
    from scripts.backup.medallion_backup import reconcile, s3_inventory

    source = Path("/drill/input")
    root = settings.BASE_DIR
    if sys.argv[1] == "wait":
        with closing(S3Storage().client) as client:
            for _ in range(60):
                try:
                    client.head_bucket(Bucket=settings.S3_BUCKET_BRONZE)
                    return
                except Exception:
                    time.sleep(1)
        raise RuntimeError("Restored MinIO did not become ready")
    if sys.argv[1] == "seed":
        import geopandas as gpd
        from shapely.geometry import box
        from climate_platform.repositories.access_repository import initialize_access_store

        with closing(S3Storage().client) as client:
            for _ in range(60):
                try:
                    client.list_buckets()
                    break
                except Exception:
                    time.sleep(1)
            for bucket in ("drill-bronze", "drill-silver", "drill-gold", "drill-warehouse"):
                client.create_bucket(Bucket=bucket)
                client.put_bucket_versioning(
                    Bucket=bucket, VersioningConfiguration={"Status": "Enabled"}
                )
            # Deliberately retain old versions and a delete marker, outside ingestion mappings.
            for data in (b"original", b"corrected"):
                client.put_object(Bucket="drill-bronze", Key="history", Body=data)
            client.delete_object(Bucket="drill-bronze", Key="history")
        folder = source / "bronze/data/shp/USDM_20200107_M"
        folder.mkdir(parents=True)
        gpd.GeoDataFrame(
            {"DM": [1, 4]},
            geometry=[box(-102, 33, -98, 37), box(-101, 34, -99, 36)],
            crs="EPSG:4326",
        ).to_file(folder / "USDM_20200107.shp")
        grid = source / "gold/data/usdmfinal.csv"
        grid.parent.mkdir(parents=True)
        grid.write_text("grid,lon,lat\nA,-100,35\nB,-120,40\n", encoding="utf-8")
        first = run_pipeline(source, root / "products", sys.executable)
        assert first["succeeded"] == 1 and first["failed"] == 0, first
        initialize_access_store()
        with closing(S3Storage().client) as client:
            Path("/drill/versions.json").write_text(
                json.dumps(s3_inventory(client)), encoding="utf-8"
            )
    else:
        import httpx

        with closing(S3Storage().client) as client:
            result = reconcile(root, s3_client=client)
        assert result["s3_objects_pending_live_verification"] == 0
        assert result["builds"] == 1 and result["gold_rows"] == 2
        replay = run_pipeline(source, root / "products", sys.executable)
        assert replay["skipped"] == 1 and replay["failed"] == 0, replay
        with closing(sqlite3.connect(root / "metadata/ingestion.sqlite3")) as db:
            file_id, revision = db.execute("SELECT file_id,revision FROM observations").fetchone()
        with httpx.Client(base_url="http://restored-api:8000", timeout=10) as client:
            for _ in range(60):
                try:
                    ready = client.get("/readyz")
                    if ready.status_code == 200 and ready.json()["status"] == "ok":
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("Restored API not ready")
            raw = root / "replay.zip"
            package_raw(source / "bronze/data/shp/USDM_20200107_M/USDM_20200107.shp", raw)
            with raw.open("rb") as stream:
                response = client.post(
                    "/upload",
                    headers={"X-API-Key": "restore.fixture-secret"},
                    files={"file": ("USDM_20200107_M.zip", stream)},
                    data={
                        "source": "usdm",
                        "source_date": "2020-01-07",
                        "dataset_key": DATASET_KEY,
                    },
                )
            response.raise_for_status()
            receipt = response.json()
            assert receipt["status"] == "DUPLICATE"
            assert (receipt["metadata"]["file_id"], receipt["metadata"]["revision"]) == (
                file_id,
                revision,
            )
        print(
            json.dumps(
                {
                    "status": "passed",
                    "scope": "isolated real MinIO, synthetic GIS",
                    "reconciliation": result,
                    "duplicate_file_id": file_id,
                }
            )
        )


if __name__ == "__main__":
    main()
