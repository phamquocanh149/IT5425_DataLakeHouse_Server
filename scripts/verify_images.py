"""Fail closed on image origin/digest, scan findings or missing SBOM tooling.

Run before deployment: python scripts/verify_images.py
Requires docker and Trivy on PATH. Does not start or replace any containers.
"""

import json
import os
from pathlib import Path
import re
import subprocess

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    values = {**dotenv_values(ROOT / ".env"), **os.environ}
    output = ROOT / "security-artifacts"
    output.mkdir(exist_ok=True)
    evidence = []
    for repo, variable in (("minio", "MINIO_DIGEST"), ("mc", "MINIO_MC_DIGEST")):
        digest = values.get(variable, "")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise SystemExit(
                f"{variable} must be a verified sha256 digest from quay.io/minio/{repo}"
            )
        image = f"quay.io/minio/{repo}@{digest}"
        # Resolve and pull by digest from the official namespace; no third-party mirror fallback.
        subprocess.run(["docker", "pull", image], check=True)
        subprocess.run(
            [
                "trivy",
                "image",
                "--format",
                "cyclonedx",
                "--output",
                str(output / f"{repo}.cdx.json"),
                image,
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
                image,
            ],
            check=True,
        )
        evidence.append({"image": image, "origin": "quay.io/minio", "scan": "passed"})
    (output / "verified-images.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
