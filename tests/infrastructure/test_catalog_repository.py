"""Unit tests for registry initialization/read paths used by the publish worker."""

from __future__ import annotations

from climate_platform.repositories.catalog_repository import MetadataManager


def test_initialize_once_runs_schema_setup_only_once(tmp_path, monkeypatch):
    manager = MetadataManager(metadata_dir=tmp_path)
    calls = []
    monkeypatch.setattr(manager, "initialize", lambda: calls.append(1))

    manager.initialize_once()
    manager.initialize_once()

    assert calls == [1]


def test_list_all_can_use_read_only_connection(tmp_path):
    manager = MetadataManager(metadata_dir=tmp_path)
    manager.initialize()

    assert manager.list_all(read_only=True) == []
