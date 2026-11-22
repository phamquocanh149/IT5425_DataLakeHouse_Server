"""Restore a verified checkpoint to a NEW root and record measured data recovery time.

This does not start services or certify host independence. Service RTO, duplicate upload,
and live MinIO verification remain separate acceptance gates in the Stage 5 runbook.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.medallion_backup import restore, verify, sha256, distinct_paths  # noqa: E402


def recovery_age(checkpoint, incident):
    start, end = datetime.fromisoformat(checkpoint), datetime.fromisoformat(incident)
    if start.tzinfo is None or end.tzinfo is None or end < start:
        raise ValueError("Incident must be timezone-aware and at/after checkpoint")
    return (end - start).total_seconds()


def drill(bundle, target, report, *, verified_copy=None, incident=None):
    distinct_paths([bundle, target, report] + ([verified_copy] if verified_copy else []))
    if report.exists():
        raise ValueError("Report must be NEW")
    started = datetime.now(timezone.utc).isoformat()
    if incident:
        instant = datetime.fromisoformat(incident)
        if instant.tzinfo is None or instant > datetime.now(timezone.utc):
            raise ValueError("Incident must have a timezone and cannot be in the future")
    clock = time.monotonic()
    manifest = verify(bundle)
    copy_verified = False
    if verified_copy:
        verify(verified_copy)
        if sha256(bundle / "manifest.json") != sha256(verified_copy / "manifest.json"):
            raise ValueError("Off-host copy is a different checkpoint")
        copy_verified = True
    age = recovery_age(manifest["checkpoint_utc"], incident or started)
    result = restore(verified_copy or bundle, target)
    elapsed = time.monotonic() - clock
    evidence = {
        "checkpoint_utc": manifest["checkpoint_utc"],
        "recovery_started_utc": started,
        "data_verified_utc": datetime.now(timezone.utc).isoformat(),
        "checkpoint_sha256": sha256(bundle / "manifest.json"),
        "images": manifest["images"],
        "reconciliation": result,
        "incident_utc": incident,
        "checkpoint_age_seconds": age,
        "rpo_seconds": age if incident else None,
        "rpo_24h_target_met": age <= 86400 if incident else None,
        "data_recovery_seconds": elapsed,
        "data_recovery_2h_target_met": elapsed <= 7200,
        "copy_bytes_verified": copy_verified,
        "offhost_location_independence": "requires operator/infrastructure evidence",
        "service_rto_seconds": None,
        "production_acceptance": "pending",
        "remaining_gates": ["service readiness and duplicate upload", "off-host location evidence"]
        + (["live MinIO versions/delete markers"] if manifest["backend"] == "s3" else []),
    }
    with report.open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, indent=2)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--verified-copy", type=Path)
    parser.add_argument("--incident-at")
    args = parser.parse_args()
    print(
        json.dumps(
            drill(
                args.bundle,
                args.target,
                args.report,
                verified_copy=args.verified_copy,
                incident=args.incident_at,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
