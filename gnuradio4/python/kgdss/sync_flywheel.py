#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Silent flywheel tracker for scheduled multi-burst sync.

Tracks predicted burst epochs from ``derive_sync_schedule()`` without any
on-air or protocol-visible sync-loss signalling. Missed bursts advance the
internal epoch index silently and widen the next search window. Diagnostics
are emitted only when ``KGDSS_DIAG=1``.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional, Sequence

try:
    from .p372_baseline import load_p372_params
except ImportError:
    from p372_baseline import load_p372_params  # type: ignore


@dataclass(frozen=True)
class FlywheelTarget:
    """Current flywheel search target for one scheduled burst epoch."""

    epoch_index: int
    predicted_epoch_ms: int
    search_window_half_width_s: float
    search_start_ms: int
    search_end_ms: int


@dataclass(frozen=True)
class FlywheelConfig:
    search_window_initial_s: float
    window_widen_factor: float
    window_max_s: float
    max_consecutive_misses: int


def load_flywheel_config() -> FlywheelConfig:
    """Load flywheel parameters from ``p372_baseline_config.json``."""
    params = load_p372_params()
    return FlywheelConfig(
        search_window_initial_s=float(params.flywheel_search_window_initial_s),
        window_widen_factor=float(params.flywheel_window_widen_factor),
        window_max_s=float(params.flywheel_window_max_s),
        max_consecutive_misses=int(params.flywheel_max_consecutive_misses),
    )


class SyncBurstFlywheel:
    """
    Silent flywheel tracker for a precomputed sync burst schedule.

    The receiver calls ``current_target()`` to obtain the predicted epoch and
    search window, ``on_burst_detected()`` when correlation succeeds within the
    window, and ``on_epoch_elapsed(now_ms)`` when the window closes without a
    detection. No on-air events are produced.
    """

    def __init__(
        self,
        epochs_ms: Sequence[int],
        *,
        search_window_initial_s: Optional[float] = None,
        window_widen_factor: Optional[float] = None,
        window_max_s: Optional[float] = None,
        max_consecutive_misses: Optional[int] = None,
    ) -> None:
        self._epochs = [int(t) for t in epochs_ms]
        cfg = load_flywheel_config()
        self._initial_window_s = float(
            cfg.search_window_initial_s
            if search_window_initial_s is None
            else search_window_initial_s
        )
        self._window_widen_factor = float(
            cfg.window_widen_factor
            if window_widen_factor is None
            else window_widen_factor
        )
        self._window_max_s = float(
            cfg.window_max_s if window_max_s is None else window_max_s
        )
        self._max_consecutive_misses = int(
            cfg.max_consecutive_misses
            if max_consecutive_misses is None
            else max_consecutive_misses
        )
        if self._initial_window_s <= 0:
            raise ValueError("search_window_initial_s must be > 0")
        if self._window_widen_factor < 1.0:
            raise ValueError("window_widen_factor must be >= 1.0")
        if self._window_max_s < self._initial_window_s:
            raise ValueError("window_max_s must be >= search_window_initial_s")
        if self._max_consecutive_misses <= 0:
            raise ValueError("max_consecutive_misses must be > 0")

        self._index = 0
        self._consecutive_misses = 0
        self._window_half_s = self._initial_window_s
        self._total_missed = 0
        self._cold_start = False

    @property
    def current_epoch_index(self) -> int:
        return self._index

    @property
    def consecutive_misses(self) -> int:
        return self._consecutive_misses

    @property
    def total_missed(self) -> int:
        return self._total_missed

    @property
    def in_cold_start(self) -> bool:
        return self._cold_start

    def _diag(self, message: str) -> None:
        if os.environ.get("KGDSS_DIAG") == "1":
            sys.stderr.write(
                f"[kgdss-flywheel] index={self._index} misses={self._consecutive_misses} "
                f"window_half_s={self._window_half_s:.6f} {message}\n"
            )

    def _half_width_ms(self) -> float:
        return self._window_half_s * 1000.0

    def current_target(self) -> Optional[FlywheelTarget]:
        if self._index >= len(self._epochs):
            return None
        epoch = self._epochs[self._index]
        half_ms = self._half_width_ms()
        return FlywheelTarget(
            epoch_index=self._index,
            predicted_epoch_ms=epoch,
            search_window_half_width_s=self._window_half_s,
            search_start_ms=int(round(epoch - half_ms)),
            search_end_ms=int(round(epoch + half_ms)),
        )

    def on_burst_detected(self, timestamp_ms: int) -> Optional[FlywheelTarget]:
        """
        Record a burst detection at ``timestamp_ms`` (ms since session start).

        When the timestamp falls inside the current search window, advance to the
        next epoch, reset the consecutive miss counter, and tighten the window
        back to its initial half-width.
        """
        target = self.current_target()
        if target is None:
            return None
        ts = int(timestamp_ms)
        if ts < target.search_start_ms or ts > target.search_end_ms:
            return target

        self._consecutive_misses = 0
        self._window_half_s = self._initial_window_s
        self._cold_start = False
        self._index += 1
        self._diag(f"detected burst at {ts}ms")
        return self.current_target()

    def on_epoch_elapsed(self, now_ms: int) -> Optional[FlywheelTarget]:
        """
        Close the search window for the current epoch without a detection.

        Increments the miss counter, widens the next window, and advances the
        epoch index silently. After ``max_consecutive_misses``, resets to a
        cold-start state (no on-air signalling).
        """
        target = self.current_target()
        if target is None:
            return None
        now = int(now_ms)
        if now < target.search_end_ms:
            return target

        missed_index = target.epoch_index
        self._consecutive_misses += 1
        self._total_missed += 1
        self._window_half_s = min(
            self._window_max_s,
            self._window_half_s * self._window_widen_factor,
        )
        self._index += 1
        self._diag(f"missed epoch {missed_index} at now={now}ms")

        if self._consecutive_misses >= self._max_consecutive_misses:
            self._cold_start_reset(now)

        return self.current_target()

    def _cold_start_reset(self, now_ms: int) -> None:
        self._diag("cold-start reset")
        self._consecutive_misses = 0
        self._window_half_s = self._initial_window_s
        self._cold_start = True
        self._index = 0
        while self._index < len(self._epochs):
            target = self.current_target()
            if target is None or now_ms <= target.search_end_ms:
                break
            self._index += 1
