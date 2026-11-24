"""Shared filesystem helpers.

Path containment is a pure, security-sensitive helper needed by the release store and the
portal services; it lives in ``common`` so neither has to import the other.
"""

from pathlib import Path

from climate_platform.common.errors import PortalError


def contained(root, relative):
    """Resolve ``relative`` under ``root``; reject escapes and symlinked components.

    Only components *below* ``root`` are checked for symlinks: a legitimate ancestor of
    ``root`` may itself be a symlink (e.g. macOS ``/var`` -> ``/private/var``, ``/tmp``),
    and a symlinked component below ``root`` that escapes is already rejected by the
    resolved-containment check. ``root`` itself may be a symlink.
    """
    root = Path(root)
    path = root / relative
    resolved = path.resolve()
    resolved_root = root.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise PortalError(503, "ARTIFACT_UNAVAILABLE")
    current = path
    while current != root and root in current.parents:
        if current.is_symlink():
            raise PortalError(503, "ARTIFACT_UNAVAILABLE")
        current = current.parent
    return resolved
