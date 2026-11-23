"""Run with the wheel interpreter and -I from outside the checkout."""

import hashlib
from contextlib import chdir
from importlib import metadata, resources
import json
import os
from pathlib import Path
import tempfile


def main():
    with tempfile.TemporaryDirectory(prefix="phase1-package-") as directory, chdir(directory):
        os.environ.update(
            BASE_DIR=directory,
            STORAGE_BACKEND="local",
            DEBUG="False",
            API_KEYS="[]",
            ENABLE_STATIC_KEYS="True",
            ENABLE_LEGACY_KEYS="False",
            COLLECTOR_API_KEY="package-only-collector",
            ADMIN_API_KEY="package-only-admin",
            PORTAL_ENABLED="False",
        )
        import climate_platform
        from climate_platform.api.app import app
        from climate_platform.config import CHECKOUT_ROOT
        from fastapi.testclient import TestClient

        assert CHECKOUT_ROOT is None, "Smoke must exercise an installed wheel"
        assert "site-packages" in Path(climate_platform.__file__).parts
        package = resources.files("climate_platform").joinpath("datasets/usdm/resources")
        provenance = json.loads(package.joinpath("PROVENANCE.json").read_text())
        assert (
            hashlib.sha256(package.joinpath("usdm_bronze_to_silver.py").read_bytes()).hexdigest()
            == provenance["sha256"]
        )
        for name, item in provenance["historical_recipes"].items():
            assert hashlib.sha256(package.joinpath(name).read_bytes()).hexdigest() == item["sha256"]
        commands = {
            entry.name: entry for entry in metadata.distribution("climate-platform").entry_points
        }
        for name in ("climate-platform", "climate-usdm-worker", "climate-usdm-replay"):
            assert callable(commands[name].load())
        with TestClient(app) as client:
            assert client.get("/readyz").status_code == 200
            payload = b"date,value\n2020-01-07,1\n"
            for expected in ("VERIFIED", "DUPLICATE"):
                response = client.post(
                    "/upload",
                    headers={"X-API-Key": "package-only-collector"},
                    data={"source": "usdm", "source_date": "2020-01-07"},
                    files={"file": ("fixture.csv", payload, "text/csv")},
                )
                assert response.status_code == 200, response.text
                body = response.json()
                assert body["status"] == expected, body
                assert body["metadata"]["sha256"] == hashlib.sha256(payload).hexdigest()
        print("PASS: installed wheel, resources, entry points, API readiness/upload/duplicate/hash")


if __name__ == "__main__":
    main()
