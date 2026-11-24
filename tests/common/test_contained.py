"""Regression guards for ``contained`` path resolution.

The original helper rejected paths whose *ancestors* were symlinks, which broke every
release/portal read on macOS (``/var`` -> ``/private/var``) and under a symlinked root.
These tests pin the corrected contract: escapes and symlinks *below* the root are rejected,
while a legitimate symlinked ancestor (or a symlinked root) is accepted.
"""

from pathlib import Path

import pytest

from climate_platform.common.errors import PortalError
from climate_platform.common.fs import contained


def _make_symlink(source, target):
    try:
        Path(source).symlink_to(target, target_is_directory=Path(target).is_dir())
    except (OSError, NotImplementedError):  # pragma: no cover - platform dependent
        pytest.skip("symlinks are unavailable in this environment")


def test_contained_accepts_symlinked_root(tmp_path):
    real = tmp_path / "real"
    (real / "releases").mkdir(parents=True)
    (real / "releases" / "r.txt").write_text("ok", encoding="utf-8")
    link = tmp_path / "link"
    _make_symlink(link, real)

    resolved = contained(link, "releases/r.txt")
    assert resolved.read_text(encoding="utf-8") == "ok"


def test_contained_rejects_escape(tmp_path):
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")
    with pytest.raises(PortalError):
        contained(root, "../outside.txt")


def test_contained_rejects_symlink_below_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    _make_symlink(root / "escape", outside)

    with pytest.raises(PortalError):
        contained(root, "escape")
