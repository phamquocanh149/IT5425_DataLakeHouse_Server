"""Optional-dependency guard for the NLDAS layers.

One job: check that the interpreter running processing has the scientific stack the layer
needs, and fail with a clear message instead of an ImportError deep in the science.
"""

from __future__ import annotations


def require(modules, purpose):
    missing = []
    for name in modules:
        try:
            __import__(name)
        except ModuleNotFoundError:
            missing.append(name)
    if missing:
        raise RuntimeError(
            f"{purpose} requires {', '.join(modules)} in the running interpreter; "
            f"missing: {', '.join(missing)}"
        )
