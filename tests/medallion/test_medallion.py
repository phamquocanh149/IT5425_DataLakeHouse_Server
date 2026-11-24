"""Tests for the medallion framework layer (contracts, io, lock, paths, publisher, runner)."""

import json

import pytest

from climate_platform.medallion import (
    AllOf,
    FunctionGate,
    Layer,
    MedallionRunner,
    MedallionPaths,
    Readiness,
    RunReport,
    exclusive_run,
    publish_atomic,
    write_json_atomic,
)
from climate_platform.medallion.io import (
    atomic_write,
    file_hash,
    outputs_complete,
    read_json,
    write_completion_marker,
    write_text_atomic,
)


def test_write_json_atomic_roundtrip(tmp_path):
    target = tmp_path / "nested" / "report.json"
    write_json_atomic(target, {"b": 2, "a": 1})
    assert read_json(target) == {"a": 1, "b": 2}
    assert not list(target.parent.glob("*.tmp"))


def test_atomic_write_replaces_on_success_and_never_partial(tmp_path):
    target = tmp_path / "out.bin"
    target.write_bytes(b"old")
    with atomic_write(target) as temporary:
        temporary.write_bytes(b"new")
    assert target.read_bytes() == b"new"
    assert not list(tmp_path.glob("*.tmp"))

    with pytest.raises(RuntimeError):
        with atomic_write(target) as temporary:
            temporary.write_bytes(b"half")
            raise RuntimeError("interrupted")
    assert target.read_bytes() == b"new"  # previous content untouched
    assert not list(tmp_path.glob("*.tmp"))


def test_write_text_atomic_roundtrip(tmp_path):
    target = tmp_path / "nested" / "note.txt"
    write_text_atomic(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"


def test_outputs_complete_requires_marker_and_matching_size(tmp_path):
    assert outputs_complete(tmp_path, "_complete.json", ("a.parquet",)) is False
    path = tmp_path / "a.parquet"
    path.write_bytes(b"abc")
    write_completion_marker(tmp_path, "_complete.json", {"a.parquet": path})
    assert outputs_complete(tmp_path, "_complete.json", ("a.parquet",)) is True
    path.write_bytes(b"ab")  # truncated after the marker
    assert outputs_complete(tmp_path, "_complete.json", ("a.parquet",)) is False


def test_file_hash_matches_content(tmp_path):
    path = tmp_path / "blob"
    path.write_bytes(b"payload")
    assert file_hash(path) == file_hash(tmp_path / "blob")


def test_exclusive_run_reports_contention_and_releases(tmp_path):
    lock = tmp_path / "run.lock"
    with pytest.raises(RuntimeError):
        with exclusive_run(lock):
            with pytest.raises(OSError):
                with exclusive_run(lock):
                    pass
            raise RuntimeError()
    with exclusive_run(lock):
        pass


def test_paths_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("NOAA_SILVER_ROOT", str(tmp_path / "env-silver"))
    paths = MedallionPaths("noaa", bronze=tmp_path / "explicit-bronze")
    assert paths.root(Layer.BRONZE) == tmp_path / "explicit-bronze"
    assert paths.root(Layer.SILVER) == tmp_path / "env-silver"
    assert paths.env_name(Layer.GOLD) == "NOAA_GOLD_ROOT"


def test_paths_default_under_base(tmp_path):
    paths = MedallionPaths("usgs", base=tmp_path)
    assert paths.root(Layer.GOLD) == tmp_path / "gold" / "usgs"


def test_publish_atomic_new_adopt_and_mismatch(tmp_path):
    source = tmp_path / "built.bin"
    source.write_bytes(b"v1")
    digest = file_hash(source)
    destination = tmp_path / "products" / "a.bin"
    publish_atomic(source, destination, digest)
    assert destination.read_bytes() == b"v1"
    publish_atomic(source, destination, digest)  # idempotent adoption
    with pytest.raises(ValueError):
        publish_atomic(source, destination, "different-digest")


def test_gate_allof_first_failure():
    gate = AllOf(
        [
            FunctionGate(lambda: Readiness(True, "", {"a": 1})),
            FunctionGate(lambda: Readiness(False, "not ready", {"b": 2})),
        ]
    )
    result = gate.check()
    assert result.ready is False
    assert result.reason == "not ready"
    assert result.details == {"a": 1, "b": 2}


def _runner(tmp_path, *, built, stop_on_failure=False):
    order = ["silver", "gold"]
    calls = []

    def make(name):
        def step():
            calls.append(name)
            return built[name]

        return step

    runner = MedallionRunner(
        lock_path=tmp_path / "run.lock",
        order=order,
        log=lambda message: None,
        lock_message="busy",
        stop_on_failure=stop_on_failure,
    )
    steps = {name: make(name) for name in order}
    return runner, steps, calls


def test_runner_skips_unplanned_and_records_built(tmp_path):
    runner, steps, calls = _runner(tmp_path, built={"silver": "s", "gold": None})
    report = RunReport("noaa", ready=True, planned={"silver": True, "gold": False})
    runner.run(report, steps)
    assert calls == ["silver"]
    assert report.built == {"silver": True}
    assert report.details["artifacts"] == {"silver": "s"}


def test_runner_records_failure_and_stop_on_failure(tmp_path):
    def boom():
        raise ValueError("kaboom")

    runner = MedallionRunner(
        lock_path=tmp_path / "run.lock",
        order=["silver", "gold"],
        log=lambda message: None,
        lock_message="busy",
        stop_on_failure=True,
    )
    report = RunReport("usgs", ready=True, planned={"silver": True, "gold": True})
    tail = []

    def gold():
        tail.append("gold")
        return "g"

    runner.run(report, {"silver": boom, "gold": gold})
    assert report.failures["silver"] == "ValueError: kaboom"
    assert tail == []
    assert "gold" not in report.built


def test_runner_dry_run_and_not_ready_are_noops(tmp_path):
    runner, steps, calls = _runner(tmp_path, built={"silver": "s", "gold": "g"})
    not_ready = RunReport("noaa", ready=False, planned={"silver": True, "gold": True})
    dry = RunReport("noaa", ready=True, dry_run=True, planned={"silver": True, "gold": True})
    runner.run(not_ready, steps)
    runner.run(dry, steps)
    assert calls == []


def test_runner_lock_contention_is_runtime_error(tmp_path):
    runner, steps, _ = _runner(tmp_path, built={"silver": "s", "gold": "g"})
    report = RunReport("noaa", ready=True, planned={"silver": True, "gold": False})
    with exclusive_run(tmp_path / "run.lock"):
        with pytest.raises(RuntimeError, match="busy"):
            runner.run(report, steps)


def test_run_report_as_dict_is_json_safe():
    report = RunReport("noaa", ready=True, planned={"silver": True}, details={"calendar": "none"})
    assert json.loads(json.dumps(report.as_dict()))["calendar"] == "none"
