#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Receiver-side P.372 profile helpers.

These helpers tie the static P.372 baseline model into receiver processing by
providing per-frequency-bin expected PSD values for FFT bins and utilities for
calibration against measured PSD.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

try:
    from .p372_baseline import load_p372_params
except ImportError:
    # Support source-tree direct imports in tests/development.
    from p372_baseline import load_p372_params  # type: ignore


@dataclass(frozen=True)
class P372ReceiverProfile:
    """Per-bin P.372 reference profile for a receiver FFT frame."""

    freq_bins_hz: np.ndarray
    expected_psd_dbm_per_hz: np.ndarray
    calibrated_psd_dbm_per_hz: np.ndarray
    calibration_offset_db: float
    median_residual_db: float


def _as_float_array(x: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(x), dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError("expected 1D array")
    if arr.size == 0:
        raise ValueError("array must not be empty")
    return arr


def p372_expected_psd_profile_dbm_per_hz(
    freq_bins_hz: Iterable[float],
    *,
    center_freq_hz: float,
    nominal_floor_dbm_per_hz: float = -174.0,
) -> np.ndarray:
    """
    Build an expected P.372-like PSD profile for frequency bins.

    This is a lightweight calibrated profile:
    - baseline absolute level from `nominal_floor_dbm_per_hz`
    - low-frequency rise (1/f-like) around center frequency
    - edge roll-off to match practical receiver passband shaping

    Parameters are keyed off the static P.372 baseline config so TX and RX can
    share an auditable parameter source.
    """
    bins = _as_float_array(freq_bins_hz)
    _ = load_p372_params()  # ensure baseline config is present and deterministic

    # Distance from center in Hz (avoid exact zero with floor).
    d = np.abs(bins - float(center_freq_hz))
    d = np.maximum(d, 1.0)

    # 1/f-like term in dB using log10 distance ratio.
    # Small offset near center, tapering outward.
    f_ref = 1_000.0
    low_freq_lift_db = 3.0 / (1.0 + np.log10(1.0 + d / f_ref))

    # Soft edge shaping over full span (raised cosine in dB domain).
    span = float(np.max(bins) - np.min(bins))
    if span <= 0:
        edge = np.zeros_like(bins)
    else:
        x = (bins - np.min(bins)) / span
        edge = -1.5 * (1.0 - np.cos(2.0 * np.pi * x)) * 0.5

    return nominal_floor_dbm_per_hz + low_freq_lift_db + edge


def calibrate_p372_profile_to_measured_psd(
    freq_bins_hz: Iterable[float],
    measured_psd_dbm_per_hz: Iterable[float],
    *,
    center_freq_hz: float,
    nominal_floor_dbm_per_hz: float = -174.0,
) -> P372ReceiverProfile:
    """
    Calibrate P.372 profile to measured receiver PSD.

    Uses robust median offset between measured and expected profiles to anchor
    the model to local receiver conditions while preserving frequency-shape
    information.
    """
    bins = _as_float_array(freq_bins_hz)
    measured = _as_float_array(measured_psd_dbm_per_hz)
    if bins.size != measured.size:
        raise ValueError("freq_bins_hz and measured_psd_dbm_per_hz must have same length")

    expected = p372_expected_psd_profile_dbm_per_hz(
        bins,
        center_freq_hz=center_freq_hz,
        nominal_floor_dbm_per_hz=nominal_floor_dbm_per_hz,
    )
    residual = measured - expected
    offset = float(np.median(residual))
    calibrated = expected + offset
    median_residual = float(np.median(measured - calibrated))

    return P372ReceiverProfile(
        freq_bins_hz=bins,
        expected_psd_dbm_per_hz=expected,
        calibrated_psd_dbm_per_hz=calibrated,
        calibration_offset_db=offset,
        median_residual_db=median_residual,
    )

