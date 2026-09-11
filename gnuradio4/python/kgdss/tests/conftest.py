# SPDX-License-Identifier: GPL-3.0-or-later
"""Put gnuradio4/python ahead of other path entries for package resolution."""

from __future__ import annotations

import sys
from pathlib import Path

_GR4_PYTHON = Path(__file__).resolve().parents[2]
_GR4_PYTHON_STR = str(_GR4_PYTHON)
# Prefer GR4 python/ over any other kgdss install on PYTHONPATH.
while _GR4_PYTHON_STR in sys.path:
    sys.path.remove(_GR4_PYTHON_STR)
sys.path.insert(0, _GR4_PYTHON_STR)
