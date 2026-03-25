#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P.372 baseline parameter source (static, precomputed).

This module intentionally does not attempt to implement the full ITU-R P.372-15
model. Instead, it provides a single authoritative loader for a precomputed
parameter set (nominal averages and conservative minimum-case constraints) used
by sync-burst scheduling and noise-mimicry helpers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
    Load precomputed P.372-derived parameters from a static JSON config.

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

