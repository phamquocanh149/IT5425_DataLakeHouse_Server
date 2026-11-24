"""Default-run guards for the USDM drought-classification contract.

``pytest -q`` must not silently skip the science: these tests run with no GIS stack. They pin
the frozen worker bytes and assert the classification rules it must keep — max severity for
overlapping polygons, no-polygon ``"0"``, ``D0``..``D4`` labels, the ``DM`` 0..4 domain and the
Gold completeness gate. The end-to-end GIS run lives in ``test_usdm_gis``.
"""

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCIENCE = REPO_ROOT / "src/climate_platform/datasets/usdm/science.py"

# Byte-pinned classification worker. A change to the drought science must be reviewed and
# this hash updated in the same commit, exactly like the vendored cleaner PROVENANCE.
SCIENCE_SHA256 = "10be63a92cf68819c79b58c93269ecd39d40f5324684ab82c9d40dd34c0b70ce"

CATEGORIES = ["0", "D0", "D1", "D2", "D3", "D4"]


def drought_label(dm_value):
    """Mirror of ``science.process``: outside all polygons -> ``"0"``, else ``D<dm>``."""
    if dm_value is None or dm_value != dm_value:  # NaN
        return "0"
    return f"D{int(dm_value)}"


def classify_cell(dm_values):
    """Mirror of ``science.process``: overlapping polygons take the maximum ``DM``."""
    present = [value for value in dm_values if value is not None and value == value]
    return drought_label(max(present)) if present else "0"


def dm_in_domain(values):
    """Mirror of ``science.process``: ``DM`` must be an integer from 0 through 4."""
    return all(value is not None and value == int(value) and 0 <= value <= 4 for value in values)


def test_science_worker_is_byte_pinned():
    digest = hashlib.sha256(SCIENCE.read_bytes()).hexdigest()
    assert digest == SCIENCE_SHA256, "science.py classification changed without review"


def test_drought_classification_contract():
    assert classify_cell([]) == "0"  # outside every polygon is no drought
    assert classify_cell([0]) == "D0"  # DM 0 is abnormally dry, not "0"
    assert classify_cell([1, 4]) == "D4"  # overlap uses the maximum severity
    assert classify_cell([4, 1]) == "D4"
    assert classify_cell([None, 2]) == "D2"  # a miss does not cancel a hit
    assert [drought_label(v) for v in range(5)] == CATEGORIES[1:]  # D0..D4
    assert drought_label(None) == "0"

    assert dm_in_domain([0, 4, 2.0]) is True  # whole floats stay in the 0..4 domain
    assert dm_in_domain([0.5]) is False  # fractional rejected before coercion
    assert dm_in_domain([5]) is False  # out-of-range rejected
    assert dm_in_domain([-1]) is False


def test_worker_source_encodes_contract():
    source = SCIENCE.read_text(encoding="utf-8")
    # Each fragment is the worker's enforcement of one contract rule above; if the review
    # deliberately re-pins the hash, these keep the semantics from drifting.
    assert 'severity = joined.groupby("grid").dm_value.max()' in source
    assert '"0" if pd.isna(value) else f"D{int(value)}"' in source
    assert "if dm.isna().any() or not dm.isin(range(5)).all():" in source
    assert "if len(gold) != len(grid) or gold.isna().any().any():" in source
