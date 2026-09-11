# SPDX-License-Identifier: GPL-3.0-or-later
"""Load gnuradio4/python/kgdss modules by path with a working package context."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_KGDSS_DIR = Path(__file__).resolve().parents[1]
_GR4_PYTHON = _KGDSS_DIR.parent
_PKG = "kgdss"


def _ensure_package() -> ModuleType:
    if _PKG in sys.modules and getattr(sys.modules[_PKG], "__path__", None):
        path = Path(getattr(sys.modules[_PKG], "__file__", "") or "")
        if "gnuradio4" in path.parts:
            return sys.modules[_PKG]
        # Wrong kgdss (e.g. top-level); replace with GR4 package stub.
        del sys.modules[_PKG]

    init_path = _KGDSS_DIR / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        _PKG,
        init_path,
        submodule_search_locations=[str(_KGDSS_DIR)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot create package for {init_path}")
    pkg = importlib.util.module_from_spec(spec)
    pkg.__path__ = [str(_KGDSS_DIR)]  # type: ignore[attr-defined]
    sys.modules[_PKG] = pkg
    # Do not exec __init__: it rebinds key_injector to KeyInjectorBlock and
    # would pull top-level side effects. Leaf modules are loaded explicitly.
    return pkg


def load_gr4_kgdss_module(stem: str) -> ModuleType:
    """
    Load ``gnuradio4/python/kgdss/<stem>.py`` as ``kgdss.<stem>``.

    Uses a unique registration when ``stem == "key_injector"`` would be
    shadowed by the package attribute of the same name after a full __init__.
    """
    _ensure_package()
    path = _KGDSS_DIR / f"{stem}.py"
    if not path.is_file():
        raise FileNotFoundError(path)

    # Prefer a private sys.modules key for key_injector so package attribute
    # shadowing cannot replace the module object.
    mod_name = f"{_PKG}.{stem}"
    private_name = f"{_PKG}._gr4_{stem}"

    if private_name in sys.modules:
        return sys.modules[private_name]
    if mod_name in sys.modules:
        existing = sys.modules[mod_name]
        if hasattr(existing, "__file__") and "gnuradio4" in Path(existing.__file__).parts:
            return existing

    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _PKG
    sys.modules[mod_name] = mod
    sys.modules[private_name] = mod
    spec.loader.exec_module(mod)

    got = Path(mod.__file__).resolve()
    if "gnuradio4" not in got.parts or "kgdss" not in got.parts:
        raise AssertionError(f"expected gnuradio4/.../kgdss/{stem}.py, got {got}")
    return mod
