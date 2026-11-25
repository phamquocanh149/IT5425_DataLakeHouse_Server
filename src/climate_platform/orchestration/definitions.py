"""Dagster code location: four medallion assets, one shared S3 resource and a schedule."""

import os
from pathlib import Path

from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetOut,
    AssetSpec,
    Config,
    DefaultScheduleStatus,
    Definitions,
    MetadataValue,
    Output,
    RetryPolicy,
    ScheduleDefinition,
    define_asset_job,
    multi_asset,
    resource,
)

from climate_platform.config import settings
from climate_platform.modules.processing.auto_publish import (
    default_publishers,
    publish_source,
)
from climate_platform.repositories.catalog_repository import metadata_manager
from climate_platform.s3.layers import LayerStore

SOURCES = ("nldas", "noaa", "usdm", "usgs")
LAYERS = ("silver", "gold")


class PublishConfig(Config):
    cache_root: str = ""


@resource
def layer_stores(_context):
    return {
        "bronze": LayerStore(settings.S3_BUCKET_BRONZE),
        "silver": LayerStore(settings.S3_BUCKET_SILVER),
        "gold": LayerStore(settings.S3_BUCKET_GOLD),
    }


def _source_asset(source):
    @multi_asset(
        name=f"{source}_medallion",
        group_name=source,
        outs={
            layer: AssetOut(
                key=f"{source}_{layer}",
                group_name=source,
                kinds={"parquet"} if layer == "silver" else {"parquet", "csv"},
                description=f"{source} {layer} products published to MinIO",
            )
            for layer in LAYERS
        },
        deps=[AssetKey(f"{source}_bronze")],
        required_resource_keys={"layer_stores"},
        retry_policy=RetryPolicy(max_retries=2, delay=30),
        compute_kind="python",
    )
    def _asset(context: AssetExecutionContext, config: PublishConfig):
        metadata_manager.initialize_once()
        records = metadata_manager.list_all(source_filter=source, read_only=True)
        publisher = default_publishers([source])[0]
        cache_root = Path(
            config.cache_root
            or os.environ.get("MEDALLION_PUBLISH_CACHE_ROOT")
            or settings.scratch_path / "medallion-publish"
        )
        result = publish_source(
            publisher,
            records,
            stores=context.resources.layer_stores,
            cache_root=cache_root / source,
            log=context.log.info,
        )
        if result.failures:
            raise RuntimeError(f"{source} auto-publish failed: {result.failures}")
        metadata = {
            "ready": result.ready,
            "reason": result.reason,
            "bronze_records": result.bronze_records,
            "bronze_downloaded": result.bronze_downloaded,
            "bronze_cached": result.bronze_cached,
            "details": MetadataValue.json(result.details),
        }
        yield Output(
            result.silver_objects,
            output_name="silver",
            metadata={"objects": result.silver_objects, **metadata},
        )
        yield Output(
            result.gold_objects,
            output_name="gold",
            metadata={"objects": result.gold_objects, **metadata},
        )

    return _asset


source_assets = [
    AssetSpec(
        f"{source}_bronze",
        group_name=source,
        kinds={"s3"},
        description="Immutable Client uploads in the climate-bronze bucket",
    )
    for source in SOURCES
]
medallion_assets = [_source_asset(source) for source in SOURCES]

publish_all_job = define_asset_job(
    "medallion_publish_all",
    selection=[f"{source}_{layer}" for source in SOURCES for layer in LAYERS],
    description="Sync Bronze and publish Silver/Gold for every dataset.",
)
source_jobs = [
    define_asset_job(
        f"medallion_publish_{source}",
        selection=[f"{source}_silver", f"{source}_gold"],
        description=f"Sync Bronze and publish Silver/Gold for {source}.",
    )
    for source in SOURCES
]
publish_schedule = ScheduleDefinition(
    job=publish_all_job,
    cron_schedule="*/5 * * * *",
    default_status=DefaultScheduleStatus.RUNNING,
    description="Materialize every dataset's medallion every five minutes.",
)

defs = Definitions(
    assets=[*source_assets, *medallion_assets],
    jobs=[publish_all_job, *source_jobs],
    schedules=[publish_schedule],
    resources={"layer_stores": layer_stores},
)
