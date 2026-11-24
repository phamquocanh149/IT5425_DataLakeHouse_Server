import argparse
import json
import sys
import tomllib
from pathlib import Path

from climate_platform.datasets.usgs.api import API
from climate_platform.datasets.usgs.config import Config
from climate_platform.datasets.usgs.crawl import crawl, discover
from climate_platform.datasets.usgs.export import compare, export
from climate_platform.datasets.usgs.preprocess import audit_raw, preprocess
from climate_platform.datasets.usgs.validate import validate
from climate_platform.datasets.usgs.workflow import require_api_key, run_all
from climate_platform.medallion.lock import exclusive_run


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "auto":
        try:
            from climate_platform.datasets.usgs.runner_cli import main as auto_main

            return auto_main(sys.argv[2:])
        except KeyboardInterrupt:
            print("Interrupted; incomplete runs cannot be used downstream.", file=sys.stderr)
            return 130
        except Exception as exc:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    if len(sys.argv) > 1 and sys.argv[1] in {
        "silver",
        "weekly",
        "gold",
        "validate-gold",
        "build-gold",
    }:
        try:
            from climate_platform.datasets.usgs.stage_cli import main as stage_main

            return stage_main(sys.argv[1:])
        except KeyboardInterrupt:
            print("Interrupted; incomplete runs cannot be used downstream.", file=sys.stderr)
            return 130
        except Exception as exc:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    parser = argparse.ArgumentParser(
        description="USGS daily discharge: full crawl and gated station preprocessing"
    )
    parser.add_argument(
        "command",
        choices=[
            "discover",
            "crawl",
            "validate",
            "export",
            "compare",
            "preprocess",
            "audit",
            "run",
        ],
    )
    parser.add_argument("--config")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--regions", help="Comma-separated HUC2 codes")
    parser.add_argument("--output")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--requests-per-second", type=float)
    parser.add_argument("--limit-sites", type=int, help="Pilot: region round-robin subset")
    parser.add_argument("--sites", help="Comma-separated USGS- station IDs")
    parser.add_argument(
        "--max-donors", type=int, default=20, help="Donors per target/date/HUC level"
    )
    parser.add_argument("--reference", help="Manually downloaded CSV for compare command")
    args = parser.parse_args()
    values = {}
    if args.config:
        with open(args.config, "rb") as f:
            values = tomllib.load(f)
    for key in ("start", "end", "output", "workers", "requests_per_second"):
        if getattr(args, key) is not None:
            values[key] = getattr(args, key)
    if args.regions:
        values["regions"] = args.regions.split(",")
    if args.max_donors < 1:
        parser.error("--max-donors must be positive")
    if args.command != "crawl" and (args.limit_sites is not None or args.sites):
        parser.error("--limit-sites and --sites apply only to crawl")
    if args.limit_sites is not None and args.sites:
        parser.error("Choose either --limit-sites or --sites")
    if args.limit_sites is not None and args.limit_sites < 1:
        parser.error("--limit-sites must be positive")
    api = None
    lock = None
    lock_entered = False
    try:
        config = Config(**values).check()
        Path(config.output).mkdir(parents=True, exist_ok=True)
        lock = exclusive_run(Path(config.output) / ".pipeline.lock")
        try:
            lock.__enter__()
            lock_entered = True
        except OSError:
            raise RuntimeError("Another command is using this output directory") from None
        if args.command in {"discover", "crawl"}:
            if args.command == "crawl" and args.limit_sites is None and not args.sites:
                require_api_key()
            api = API(config)
            if args.command == "discover":
                rows = discover(config, api)
                print(f"Catalog: {len(rows)} series")
            else:
                crawl(config, api, args.limit_sites, args.sites.split(",") if args.sites else None)
                report = validate(config)
                print(
                    json.dumps(
                        {k: report[k] for k in ("status_counts", "unplanned_jobs", "metrics")}
                    )
                )
                if report["unresolved_jobs"]:
                    return 2
        elif args.command == "validate":
            report = validate(config)
            print(
                json.dumps(
                    {
                        k: report[k]
                        for k in ("all_jobs_successful", "status_counts", "unplanned_jobs")
                    }
                )
            )
            return 0 if report["all_jobs_successful"] else 2
        elif args.command == "run":
            print(f"Workflow completed: {run_all(config, args.max_donors)}")
        elif args.command == "preprocess":
            print(f"Preprocessing completed: {preprocess(config, args.max_donors)}")
        elif args.command == "audit":
            result = audit_raw(config)
            print(json.dumps(result))
            return 0 if result["passed"] else 2
        elif args.command == "export":
            print(f"Exported {len(export(config))} station CSVs")
        else:
            if not args.reference:
                parser.error("compare requires --reference")
            result = compare(config, args.reference)
            print(json.dumps(result))
            return 0 if result["passed"] else 2
        return 0
    except KeyboardInterrupt:
        print("Interrupted. Run crawl again to resume unfinished jobs.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if api:
            api.close()
        if lock_entered:
            lock.__exit__(None, None, None)


if __name__ == "__main__":
    sys.exit(main())
