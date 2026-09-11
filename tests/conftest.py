# Pytest configuration for gr-k-gdss tests.
# Register custom marks so "pytest -m 'not slow'" works without warnings.
# When KGDSS_REQUIRE_BINDINGS=1, fail the session if C++ bindings are missing
# instead of silently skipping binding-gated tests.
#
# Also prefer in-tree pure-Python sources over a stale system install of
# gnuradio.kgdss (C++ bindings still come from the installed extension module).

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_PYTHON = _REPO_ROOT / "python"


def _load_src_module(mod_name: str, filename: str):
    path = _SRC_PYTHON / filename
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _prefer_audit_extension() -> None:
    """Prefer the repo install_audit / build_audit extension over a stale system .so."""
    candidates = [
        _REPO_ROOT
        / "install_audit"
        / "lib"
        / "python3.12"
        / "site-packages"
        / "gnuradio"
        / "kgdss"
        / "kgdss_python.cpython-312-x86_64-linux-gnu.so",
        _REPO_ROOT
        / "build_audit"
        / "python"
        / "bindings"
        / "kgdss_python.cpython-312-x86_64-linux-gnu.so",
        _REPO_ROOT
        / "build_crypto_audit"
        / "python"
        / "bindings"
        / "kgdss_python.cpython-312-x86_64-linux-gnu.so",
    ]
    so_path = next((p for p in candidates if p.is_file()), None)
    if so_path is None:
        return
    # Ensure parent package exists first.
    try:
        import gnuradio  # noqa: F401
    except ImportError:
        return
    mod_name = "gnuradio.kgdss.kgdss_python"
    spec = importlib.util.spec_from_file_location(mod_name, so_path)
    if spec is None or spec.loader is None:
        return
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)


def _prefer_in_tree_python_sources() -> None:
    """Reload gnuradio.kgdss pure-Python modules from the repository tree."""
    _prefer_audit_extension()
    try:
        import gnuradio.kgdss as kgdss  # noqa: F401
    except ImportError:
        return

    replacements = (
        ("gnuradio.kgdss.session_key_derivation", "session_key_derivation.py"),
        ("gnuradio.kgdss.p372_baseline", "p372_baseline.py"),
        ("gnuradio.kgdss.p372_receiver_profile", "p372_receiver_profile.py"),
        ("gnuradio.kgdss.sync_burst_utils", "sync_burst_utils.py"),
        ("gnuradio.kgdss.sync_flywheel", "sync_flywheel.py"),
        ("gnuradio.kgdss.sync_burst_rx", "sync_burst_rx.py"),
        ("gnuradio.kgdss.key_injector", "key_injector.py"),
    )
    loaded = {}
    for mod_name, filename in replacements:
        mod = _load_src_module(mod_name, filename)
        if mod is not None:
            loaded[mod_name] = mod

    # Re-exec package __init__ against the freshly loaded submodules.
    init_path = _SRC_PYTHON / "__init__.py"
    if not init_path.is_file():
        return
    spec = importlib.util.spec_from_file_location(
        "gnuradio.kgdss", init_path, submodule_search_locations=[str(_SRC_PYTHON)]
    )
    if spec is None or spec.loader is None:
        return
    pkg = sys.modules.get("gnuradio.kgdss")
    if pkg is None:
        return
    # Keep the compiled extension attribute if already imported.
    ext = getattr(pkg, "kgdss_python", None)
    if ext is None:
        ext = sys.modules.get("gnuradio.kgdss.kgdss_python")
    # Point package search path at the in-tree python/ so submodule imports
    # resolve to the checkout, not a stale install.
    pkg.__path__ = [str(_SRC_PYTHON)]
    pkg.__file__ = str(init_path)
    for mod_name, mod in loaded.items():
        sys.modules[mod_name] = mod
        short = mod_name.rsplit(".", 1)[-1]
        # Drop stale submodule attributes left from the site-packages import so
        # "from gnuradio.kgdss import sync_burst_utils" does not return the old module.
        if hasattr(pkg, short):
            try:
                delattr(pkg, short)
            except AttributeError:
                pass
    spec.loader.exec_module(pkg)
    if ext is not None:
        sys.modules["gnuradio.kgdss.kgdss_python"] = ext
        if getattr(pkg, "kgdss_spreader_cc", None) is None:
            pkg.kgdss_spreader_cc = getattr(ext, "kgdss_spreader_cc", None)
            pkg.kgdss_despreader_cc = getattr(ext, "kgdss_despreader_cc", None)
            pkg.kgdss_sync_state = getattr(ext, "kgdss_sync_state", None)
    # Keep sys.modules authoritative for submodule objects. Do not setattr module
    # objects onto the package after __init__ (it exports same-named callables).
    for mod_name, mod in loaded.items():
        sys.modules[mod_name] = mod


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "slow: marks test as slow (e.g. TestT1SetKeyMessagePort, ~1 min). Skip with: pytest -m 'not slow'",
    )
    _prefer_in_tree_python_sources()


def pytest_sessionstart(session):
    """Fail loudly when CI requires compiled bindings but they are unavailable."""
    if os.environ.get("KGDSS_REQUIRE_BINDINGS", "").strip() not in (
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    ):
        return
    try:
        from gnuradio import kgdss
    except ImportError as exc:
        raise RuntimeError(
            "KGDSS_REQUIRE_BINDINGS is set but gnuradio.kgdss could not be imported: {}. "
            "Build and install the module before running this test session.".format(exc)
        ) from exc
    if getattr(kgdss, "kgdss_spreader_cc", None) is None or getattr(
        kgdss, "kgdss_despreader_cc", None
    ) is None:
        raise RuntimeError(
            "KGDSS_REQUIRE_BINDINGS is set but C++ bindings are missing "
            "(kgdss_spreader_cc / kgdss_despreader_cc are None). "
            "Build and install gnuradio-kgdss before running this test session."
        )
