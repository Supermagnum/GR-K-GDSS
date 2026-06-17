#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P.372 baseline parameter source (static, precomputed).

Integration hooks only — not ITU-R P.372-17 compliance.

P372_COMPLIANCE is ``"none"``. These modules are named ``p372_*`` for roadmap
alignment with ITU-R P.372-17; they do **not** implement the Recommendation.

Not implemented (see ``docs/todo.md``, §2.1 roadmap):
  - §3.1.1 instantaneous sky brightness temperature T_B(f)
  - §3.1.2 statistical brightness temperature T_B(f, p) / CCDF
  - ``Tmr_approx.txt`` coefficient interpolation
  - Surface weather inputs (pressure, temperature, water-vapour density)
  - Slant-path / elevation-dependent atmospheric attenuation A_T

This module loads a static JSON parameter set (nominal averages and conservative
minimum-case constraints) used by sync-burst scheduling and noise-mimicry helpers.
A future ``p372_atmospheric.py`` (or similar) should hold the real §3.1.x physics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Hooks only — not ITU §3.1.1/§3.1.2. See module docstring and docs/todo.md §2.1.
P372_COMPLIANCE = "none"


@dataclass(frozen=True)
class P372Params:
    rise_fraction: float
    pareto_alpha_nominal: float
    pareto_alpha_min: float
    mean_interval_s_nominal: float
    mean_interval_s_min: float
    min_interval_s_min: float
    lognorm_mu: float
    lognorm_sigma: float


def _config_path() -> Path:
    return Path(__file__).with_name("p372_baseline_config.json")


def load_p372_params() -> P372Params:
    """
    Load precomputed burst-scheduling parameters from static JSON.

    ``P372_COMPLIANCE`` is ``"none"`` — this is not ITU §3.1.1/§3.1.2 output.
    The file is tracked in the repository so parameterization is deterministic
    and auditable.
    """
    cfg_file = _config_path()
    raw: dict[str, Any] = json.loads(cfg_file.read_text(encoding="utf-8"))

    return P372Params(
        rise_fraction=float(raw["rise_fraction"]),
        pareto_alpha_nominal=float(raw["pareto_alpha_nominal"]),
        pareto_alpha_min=float(raw["pareto_alpha_min"]),
        mean_interval_s_nominal=float(raw["mean_interval_s_nominal"]),
        mean_interval_s_min=float(raw["mean_interval_s_min"]),
        min_interval_s_min=float(raw["min_interval_s_min"]),
        lognorm_mu=float(raw["lognorm_mu"]),
        lognorm_sigma=float(raw["lognorm_sigma"]),
    )

