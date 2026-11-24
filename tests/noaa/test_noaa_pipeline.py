"""NOAA completion/gating tests (plan layer; no pandas required).

These lock the fix that "a file exists" is never treated as "the stage is done": a stage is
complete only when its completion marker records every output at its recorded size, so an
interrupted run (no marker, or a truncated output) is rebuilt instead of silently reused.
"""

from climate_platform.datasets.noaa import pipeline, spec
from climate_platform.medallion.io import write_completion_marker


def _snapshot(tmp_path):
    snapshot = tmp_path / "bronze" / "ingest_date=2024-01-01"
    snapshot.mkdir(parents=True)
    (snapshot / "_manifest.json").write_text("{}", encoding="utf-8")
    for name in spec.REQUIRED_BRONZE_FILES:
        (snapshot / name).write_text("x", encoding="utf-8")
    return snapshot


def _context(tmp_path):
    week_dates = tmp_path / "week_dates.csv"
    week_dates.write_text("week_date\n2024-01-02\n", encoding="utf-8")
    return pipeline.NoaaContext(
        bronze_root=tmp_path / "bronze",
        silver_root=tmp_path / "silver",
        gold_root=tmp_path / "gold",
        week_dates_csv=week_dates,
        snapshot_dir=_snapshot(tmp_path),
        lock_file=tmp_path / "noaa.lock",
    )


def _write_outputs(root, names):
    root.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in names:
        path = root / name
        path.write_bytes(b"data")
        files[name] = path
    write_completion_marker(root, spec.COMPLETE_MARKER, files)
    return files


def test_files_without_marker_are_rebuilt(tmp_path):
    ctx = _context(tmp_path)
    ctx.silver_root.mkdir(parents=True)
    for name in spec.SILVER_OUTPUTS:
        (ctx.silver_root / name).write_bytes(b"data")  # bare files, no completion marker
    report = pipeline.plan(ctx)
    assert report.details["silver_present"] is False
    assert report.planned["silver"] is True


def test_completion_marker_satisfies_plan(tmp_path):
    ctx = _context(tmp_path)
    _write_outputs(ctx.silver_root, spec.SILVER_OUTPUTS)
    report = pipeline.plan(ctx)
    assert report.details["silver_present"] is True
    assert report.planned["silver"] is False


def test_truncated_output_reopens_the_stage(tmp_path):
    ctx = _context(tmp_path)
    _write_outputs(ctx.silver_root, spec.SILVER_OUTPUTS)
    (ctx.silver_root / spec.SILVER_OUTPUTS[0]).write_bytes(b"")  # truncated after the marker
    report = pipeline.plan(ctx)
    assert report.details["silver_present"] is False
    assert report.planned["silver"] is True


def test_gold_outputs_use_own_completion_marker(tmp_path):
    ctx = _context(tmp_path)
    _write_outputs(ctx.silver_root, spec.SILVER_OUTPUTS)
    report = pipeline.plan(ctx)
    assert report.details["gold_present"] is False
    assert report.planned["gold"] is True
