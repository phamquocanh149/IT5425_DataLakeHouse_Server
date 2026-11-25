"""Unit tests for the auto-publish worker lifecycle (no S3, no Dagster)."""

from __future__ import annotations

from climate_platform.modules.processing import publish_worker


def test_run_cycle_initializes_once_and_reads_registry(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        publish_worker.metadata_manager, "initialize_once", lambda: calls.append("init")
    )
    monkeypatch.setattr(
        publish_worker.metadata_manager,
        "list_all",
        lambda **kwargs: calls.append(("list", kwargs)) or [],
    )
    monkeypatch.setattr(publish_worker, "LayerStore", lambda bucket: object())
    monkeypatch.setattr(publish_worker, "default_publishers", lambda sources: [])

    assert publish_worker.run_cycle(cache_root=tmp_path) == []
    assert calls == ["init", ("list", {"read_only": True})]


def test_watch_returns_failure_exit_code_on_sigterm(monkeypatch, capsys):
    handlers = {}
    monkeypatch.setattr(
        publish_worker.signal,
        "signal",
        lambda signum, handler: handlers.__setitem__(signum, handler),
    )

    def fake_cycle(*, sources, cache_root, log):
        handlers[publish_worker.signal.SIGTERM](None, None)
        return [{"source": "usdm", "failures": {"pipeline": "boom"}}]

    monkeypatch.setattr(publish_worker, "run_cycle", fake_cycle)

    assert publish_worker.main(["--watch"]) == 1
