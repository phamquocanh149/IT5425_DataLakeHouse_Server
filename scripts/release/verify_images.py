"""Fail closed on image origin/digest, scan findings or missing SBOM tooling.

Run before deployment with --api-image and --worker-image release references.
Requires docker and Trivy on PATH. Does not start or replace any containers.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-image", required=True)
    parser.add_argument("--worker-image", required=True)
    args = parser.parse_args()
    values = {**dotenv_values(ROOT / ".env"), **os.environ}
    output = ROOT / "security-artifacts"
    output.mkdir(exist_ok=True)
    (output / "verified-images.json").unlink(missing_ok=True)
    evidence = []
    images = []
    for repo, variable in (("minio", "MINIO_DIGEST"), ("mc", "MINIO_MC_DIGEST")):
        digest = values.get(variable, "")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise SystemExit(
                f"{variable} must be a verified sha256 digest from quay.io/minio/{repo}"
            )
        image = f"quay.io/minio/{repo}@{digest}"
        # Resolve and pull by digest from the official namespace; no third-party mirror fallback.
        subprocess.run(["docker", "pull", image], check=True)
        images.append((repo, image, "quay.io/minio"))
    images.extend(
        [("api", args.api_image, "local-build"), ("worker", args.worker_image, "local-build")]
    )
    for repo, image, origin in images:
        image_id = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise RuntimeError("Missing immutable image ID")
        subprocess.run(
            [
                "trivy",
                "image",
                "--format",
                "cyclonedx",
                "--output",
                str(output / f"{repo}.cdx.json"),
                image_id,
            ],
            check=True,
        )
        subprocess.run(
            [
                "trivy",
                "image",
                "--scanners",
                "vuln",
                "--severity",
                "HIGH,CRITICAL",
                "--exit-code",
                "1",
                "--format",
                "json",
                "--output",
                str(output / f"{repo}.scan.json"),
                image_id,
            ],
            check=True,
        )
        evidence.append({"image": image, "image_id": image_id, "origin": origin, "scan": "passed"})
    (output / "verified-images.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
