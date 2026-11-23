"""Run NLDAS Bronze -> Silver -> Gold only for reference weeks that are complete.

The runner is the automation entry point: it inspects Bronze NetCDF inventory,
selects weeks whose 168 hours are all present, builds Silver for weeks that are
not yet complete, then publishes Gold for weeks whose Silver is complete. Weeks
already complete in Silver/Gold are skipped, so a scheduled rerun is cheap and
idempotent. Bronze stays read-only; only Silver/Gold partitions are written.

Example:
    python scripts/nldas/run_bronze_to_gold.py --dry-run
    python scripts/nldas/run_bronze_to_gold.py --json --report data_lake/temp/nldas.json
"""

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import gold_common
import nldas_common
import silver_common


def _empty_products(products, inventories):
    return {
        product: {
            "bronze_hours": len(inventories[product]),
            "ready_weeks": [],
            "planned_silver": [],
            "planned_gold": [],
            "built_silver": [],
            "built_gold": [],
        }
        for product in products
    }


def _base_report(args, products, inventories):
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dry_run": args.dry_run,
        "bronze_root": str(Path(args.bronze_root).resolve()),
        "references": str(Path(args.references).resolve()),
        "silver_root": str(Path(args.silver_root).resolve()),
        "gold_root": str(Path(args.gold_root).resolve()),
        "products": _empty_products(products, inventories),
        "failures": {},
    }


def _emit(report, args):
    if args.report:
        nldas_common.write_json_atomic(args.report, report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_summary(report)
    return 1 if report["failures"] else 0


def _print_summary(report):
    print(
        f"NLDAS medallion: {report['bronze_root']} -> {report['gold_root']} "
        f"({report['generated_at']})"
    )
    for product, data in report["products"].items():
        print(
            f"[{product}] bronze_hours={data['bronze_hours']} "
            f"ready={len(data['ready_weeks'])} "
            f"silver_planned={len(data['planned_silver'])} "
            f"gold_planned={len(data['planned_gold'])} "
            f"silver_built={len(data['built_silver'])} "
            f"gold_built={len(data['built_gold'])}"
        )
    for product, error in report["failures"].items():
        print(f"[{product}] FAILED: {error}", file=sys.stderr)
    if report["dry_run"]:
        print("dry-run: nothing written")


def _iso(weeks):
    return [week.isoformat() for week in sorted(weeks)]


def main(argv=None):
    nldas_common.configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", choices=("fora", "noah", "both"), default="both")
    parser.add_argument(
        "--bronze-root",
        type=Path,
        default=nldas_common.default_bronze_root(),
        help="Bronze NetCDF root (default: duy-nldas-script/src/bronze/data)",
    )
    parser.add_argument(
        "--references",
        type=Path,
        default=nldas_common.default_references(),
        help="Reference grid and Tuesday calendar directory",
    )
    parser.add_argument(
        "--silver-root",
        type=Path,
        default=nldas_common.default_silver_root(),
        help="Silver root; each product lives under <root>/<PRODUCT>",
    )
    parser.add_argument(
        "--gold-root",
        type=Path,
        default=nldas_common.default_gold_root(),
        help="Gold root; each product lives under <root>/<PRODUCT>",
    )
    parser.add_argument("--start", type=date.fromisoformat, help="First Tuesday label, YYYY-MM-DD")
    parser.add_argument("--end", type=date.fromisoformat, help="Last Tuesday label, YYYY-MM-DD")
    parser.add_argument(
        "--dry-run", action="store_true", help="Report eligible work without writing anything"
    )
    parser.add_argument("--json", action="store_true", help="Print only the JSON report to stdout")
    parser.add_argument("--report", type=Path, help="Write the JSON report to this file")
    parser.add_argument(
        "--keep-r25",
        action="store_true",
        help="Keep R25 in Gold (must match the output directory policy)",
    )
    parser.add_argument("--lock-file", type=Path, default=nldas_common.default_lock_file())
    args = parser.parse_args(argv)

    products = nldas_common.resolve_products(args.product)
    dates = nldas_common.load_week_dates(Path(args.references) / "week_dates.csv")
    if args.start:
        dates = [day for day in dates if day >= args.start]
    if args.end:
        dates = [day for day in dates if day <= args.end]
    inventories = {
        product: nldas_common.inventory(args.bronze_root, product) for product in products
    }
    ready = nldas_common.ready_weeks(dates, inventories)
    report = _base_report(args, products, inventories)
    for product in products:
        report["products"][product]["ready_weeks"] = _iso(ready[product])
    if not any(ready.values()):
        return _emit(report, args)

    try:
        grid_size = nldas_common.reference_grid_size(args.references)
        states = {}
        for product in products:
            silver_done = nldas_common.silver_complete_weeks(
                args.silver_root, product, grid_size=grid_size
            )
            gold_done = nldas_common.gold_complete_weeks(
                args.gold_root, product, grid_size=grid_size
            )
            states[product] = {
                "gold_done": gold_done,
                "silver_plan": sorted(set(ready[product]) - silver_done),
                "gold_plan": sorted(set(ready[product]) - gold_done),
            }
            report["products"][product]["planned_silver"] = _iso(states[product]["silver_plan"])
            report["products"][product]["planned_gold"] = _iso(states[product]["gold_plan"])
    except RuntimeError as exc:
        print(f"NLDAS medallion: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        return _emit(report, args)

    def log(message):
        print(message, file=sys.stderr if args.json else sys.stdout, flush=True)

    failures = {}
    try:
        with nldas_common.exclusive_run(args.lock_file):
            for product in products:
                state = states[product]
                try:
                    if state["silver_plan"]:
                        silver_common.build_silver(
                            product,
                            bronze_root=args.bronze_root,
                            references_dir=args.references,
                            silver_output=args.silver_root / product,
                            weeks=state["silver_plan"],
                            log=log,
                        )
                    silver_done = nldas_common.silver_complete_weeks(
                        args.silver_root, product, grid_size=grid_size
                    )
                    report["products"][product]["built_silver"] = _iso(
                        [day for day in state["silver_plan"] if day in silver_done]
                    )
                    gold_candidates = sorted(
                        (set(ready[product]) & silver_done) - state["gold_done"]
                    )
                    if gold_candidates:
                        gold_common.build_gold(
                            product,
                            silver_input=args.silver_root / product,
                            references_dir=args.references,
                            gold_output=args.gold_root / product,
                            weeks=gold_candidates,
                            keep_r25=args.keep_r25,
                            log=log,
                        )
                    gold_done = nldas_common.gold_complete_weeks(
                        args.gold_root, product, grid_size=grid_size
                    )
                    report["products"][product]["built_gold"] = _iso(
                        [day for day in gold_candidates if day in gold_done]
                    )
                except Exception as exc:
                    failures[product] = f"{type(exc).__name__}: {exc}"
                    log(f"[{product}] failed: {failures[product]}")
    except RuntimeError as exc:
        print(f"NLDAS medallion: {exc}", file=sys.stderr)
        return 1

    report["failures"] = failures
    return _emit(report, args)


if __name__ == "__main__":
    raise SystemExit(main())
