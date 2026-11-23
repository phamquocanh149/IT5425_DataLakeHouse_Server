import json
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.release import verify_images
from scripts.release.check_gis_report import check
from scripts.backup.recovery_drill import recovery_age


def test_vendored_cleaner_matches_reviewed_source_hash():
    root = Path(__file__).resolve().parents[2] / "src/climate_platform/datasets/usdm/resources"
    provenance = json.loads((root / "PROVENANCE.json").read_text())
    expected = provenance["sha256"]
    assert hashlib.sha256((root / "usdm_bronze_to_silver.py").read_bytes()).hexdigest() == expected
    for name, item in provenance["historical_recipes"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == item["sha256"]


def test_scan_exact_api_worker_and_storage_images(tmp_path, monkeypatch):
    monkeypatch.setattr(verify_images, "ROOT", tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["verify_images", "--api-image", "api:release", "--worker-image", "worker:release"],
    )
    monkeypatch.setenv("MINIO_DIGEST", "sha256:" + "a" * 64)
    monkeypatch.setenv("MINIO_MC_DIGEST", "sha256:" + "b" * 64)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout="sha256:" + "c" * 64)

    monkeypatch.setattr(verify_images.subprocess, "run", run)
    verify_images.main()
    evidence = json.loads((tmp_path / "security-artifacts/verified-images.json").read_text())
    assert len(evidence) == 4
    assert {item["image"] for item in evidence} >= {"api:release", "worker:release"}
    scans = [c for c in calls if c[:2] == ["trivy", "image"]]
    assert len(scans) == 8
    assert all(c[-1] == "sha256:" + "c" * 64 for c in scans)
    assert len([c for c in scans if "--exit-code" in c]) == 4

    def fail(command, **kwargs):
        raise RuntimeError("scan or image unavailable")

    monkeypatch.setattr(verify_images.subprocess, "run", fail)
    with pytest.raises(RuntimeError):
        verify_images.main()
    assert not (tmp_path / "security-artifacts/verified-images.json").exists()


@pytest.mark.parametrize("bad", ["<skipped/>", "<failure/>", "<error/>"])
def test_required_gis_rejects_skips_and_failure(tmp_path, bad):
    path = tmp_path / "report.xml"
    path.write_text("<testsuite>" + "<testcase/>" * 4 + f"<testcase>{bad}</testcase></testsuite>")
    with pytest.raises(ValueError):
        check(path)
    path.write_text("<testsuite>" + "<testcase/>" * 5 + "</testsuite>")
    check(path)


def test_rpo_measured_from_checkpoint_not_backup_completion():
    assert recovery_age("2026-11-22T00:00:00+00:00", "2026-11-22T01:00:00+00:00") == 3600
    with pytest.raises(ValueError):
        recovery_age("2026-11-22T01:00:00+00:00", "2026-11-22T00:00:00+00:00")
    with pytest.raises(ValueError):
        recovery_age("2026-11-22T00:00:00", "2026-11-22T01:00:00")
