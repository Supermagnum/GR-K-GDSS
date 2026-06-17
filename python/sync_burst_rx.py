#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RX session controller and GNU Radio block for multi-burst sync flywheel tracking.

Wires ``derive_sync_schedule``, ``derive_sync_amplitude_scaling``, and
``SyncBurstFlywheel`` into the receiver sample stream. The block advances session
time from consumed samples, closes search windows silently on miss, and accepts
burst detections via a private message port (not on-air).

Typical flowgraph wiring::

    source -> sync_burst_flywheel_rx -> ... -> kgdss_despreader_cc
    sync_burst_flywheel_rx.target -> (sync correlator / probe)
    (sync correlator) -> sync_burst_flywheel_rx.detect

The data-path despreader continues to use ``key_injector`` for GDSS masking keys.
Use ``target`` epoch_index with ``derive_sync_pn_sequence`` for sync-burst search.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from gnuradio import gr
from gnuradio.gr import pmt

try:
    from .sync_burst_utils import (
        derive_sync_amplitude_scaling,
        derive_sync_pn_sequence,
        derive_sync_schedule,
    )
    from .sync_flywheel import FlywheelTarget, SyncBurstFlywheel
except ImportError:
    from sync_burst_utils import (  # type: ignore
        derive_sync_amplitude_scaling,
        derive_sync_pn_sequence,
        derive_sync_schedule,
    )
    from sync_flywheel import FlywheelTarget, SyncBurstFlywheel  # type: ignore


def _pmt_long(value: int) -> Any:
    return pmt.from_long(int(value))


def _pmt_float(value: float) -> Any:
    return pmt.from_double(float(value))


def flywheel_target_to_pmt(
    target: FlywheelTarget,
    *,
    in_search_window: bool,
    amplitude_scale: Optional[float] = None,
) -> Any:
    """Serialize a flywheel target for GNU Radio message wiring."""
    d = pmt.make_dict()
    d = pmt.dict_add(d, pmt.intern("epoch_index"), _pmt_long(target.epoch_index))
    d = pmt.dict_add(d, pmt.intern("predicted_epoch_ms"), _pmt_long(target.predicted_epoch_ms))
    d = pmt.dict_add(
        d, pmt.intern("search_window_half_width_s"), _pmt_float(target.search_window_half_width_s)
    )
    d = pmt.dict_add(d, pmt.intern("search_start_ms"), _pmt_long(target.search_start_ms))
    d = pmt.dict_add(d, pmt.intern("search_end_ms"), _pmt_long(target.search_end_ms))
    d = pmt.dict_add(d, pmt.intern("in_search_window"), pmt.from_bool(bool(in_search_window)))
    if amplitude_scale is not None:
        d = pmt.dict_add(d, pmt.intern("amplitude_scale"), _pmt_float(amplitude_scale))
    return d


def pmt_to_detection_ms(msg: Any, *, sample_rate_hz: float, sample_offset: int) -> Optional[int]:
    """Parse a detect message into milliseconds since session start."""
    if pmt.is_dict(msg):
        if pmt.dict_has_key(msg, pmt.intern("timestamp_ms")):
            return int(pmt.to_long(pmt.dict_ref(msg, pmt.intern("timestamp_ms"), pmt.PMT_NIL)))
        if pmt.dict_has_key(msg, pmt.intern("sample_index")):
            sample_index = int(pmt.to_long(pmt.dict_ref(msg, pmt.intern("sample_index"), pmt.PMT_NIL)))
            return int(sample_index * 1000.0 / float(sample_rate_hz))
    if pmt.is_uint64(msg):
        sample_index = int(pmt.to_uint64(msg))
        return int((sample_offset + sample_index) * 1000.0 / float(sample_rate_hz))
    return None


class SyncBurstRxController:
    """
    Sample-clock-driven flywheel controller for scheduled sync bursts.

    Derives the session schedule and amplitude scales once, then tracks burst
    epochs with ``SyncBurstFlywheel``. Call ``tick_samples`` from the RX stream
    and ``notify_burst_detected`` when a sync correlator fires inside the window.
    """

    def __init__(
        self,
        sync_timing_key: bytes,
        sync_pn_key: bytes,
        session_id: int,
        sample_rate_hz: float,
        *,
        session_duration_s: float = 900.0,
        n_bursts: Optional[int] = None,
        mean_interval_s: float = 60.0,
        pareto_alpha: float = 2.0,
        min_interval_s: float = 5.0,
    ) -> None:
        if len(sync_timing_key) != 32:
            raise ValueError("sync_timing_key must be 32 bytes")
        if len(sync_pn_key) != 32:
            raise ValueError("sync_pn_key must be 32 bytes")
        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be > 0")

        self._sync_timing_key = bytes(sync_timing_key)
        self._sync_pn_key = bytes(sync_pn_key)
        self._session_id = int(session_id)
        self._sample_rate_hz = float(sample_rate_hz)

        epochs = derive_sync_schedule(
            self._sync_timing_key,
            self._session_id,
            session_duration_s=session_duration_s,
            n_bursts=n_bursts,
            mean_interval_s=mean_interval_s,
            pareto_alpha=pareto_alpha,
            min_interval_s=min_interval_s,
        )
        self._epochs_ms = list(epochs)
        self._amplitude_scales = derive_sync_amplitude_scaling(
            self._sync_timing_key,
            self._session_id,
            n_bursts,
        )
        self._flywheel = SyncBurstFlywheel(self._epochs_ms)
        self._samples = 0

    @property
    def epochs_ms(self) -> list[int]:
        return list(self._epochs_ms)

    @property
    def amplitude_scales(self) -> list[float]:
        return list(self._amplitude_scales)

    @property
    def flywheel(self) -> SyncBurstFlywheel:
        return self._flywheel

    @property
    def samples_processed(self) -> int:
        return self._samples

    def samples_to_ms(self, samples: Optional[int] = None) -> int:
        n = self._samples if samples is None else int(samples)
        return int(n * 1000.0 / self._sample_rate_hz)

    def current_target(self) -> Optional[FlywheelTarget]:
        return self._flywheel.current_target()

    def in_search_window(self, now_ms: Optional[int] = None) -> bool:
        target = self.current_target()
        if target is None:
            return False
        now = self.samples_to_ms() if now_ms is None else int(now_ms)
        return target.search_start_ms <= now <= target.search_end_ms

    def current_amplitude_scale(self) -> Optional[float]:
        target = self.current_target()
        if target is None:
            return None
        idx = target.epoch_index
        if 0 <= idx < len(self._amplitude_scales):
            return float(self._amplitude_scales[idx])
        return None

    def current_pn_sequence(self, chips: int = 10000) -> Optional[np.ndarray]:
        target = self.current_target()
        if target is None:
            return None
        return derive_sync_pn_sequence(
            self._sync_pn_key,
            self._session_id,
            chips,
            burst_index=target.epoch_index,
        )

    def tick_samples(self, n: int) -> Optional[FlywheelTarget]:
        """Advance session time by ``n`` samples; close windows that elapsed."""
        if n <= 0:
            return self.current_target()
        self._samples += int(n)
        now_ms = self.samples_to_ms()
        target = self.current_target()
        if target is None:
            return None
        if now_ms >= target.search_end_ms:
            return self._flywheel.on_epoch_elapsed(now_ms)
        return target

    def notify_burst_detected(
        self,
        *,
        timestamp_ms: Optional[int] = None,
        sample_index: Optional[int] = None,
    ) -> Optional[FlywheelTarget]:
        if timestamp_ms is None:
            if sample_index is None:
                raise ValueError("timestamp_ms or sample_index required")
            timestamp_ms = self.samples_to_ms(sample_index)
        return self._flywheel.on_burst_detected(int(timestamp_ms))


class sync_burst_flywheel_rx(gr.sync_block):
    """
    GNU Radio RX block: passthrough stream + flywheel timing for sync bursts.

    Inserts in the IQ path so sample consumption drives ``on_epoch_elapsed``.
    Connect ``detect`` to a sync correlator; subscribe to ``target`` for the
    active search window and ``epoch_index``. No on-air signalling is emitted.
    """

    def __init__(
        self,
        sync_timing_key: bytes,
        sync_pn_key: bytes,
        session_id: int,
        sample_rate_hz: float,
        *,
        session_duration_s: float = 900.0,
        n_bursts: Optional[int] = None,
        mean_interval_s: float = 60.0,
        pareto_alpha: float = 2.0,
        min_interval_s: float = 5.0,
    ) -> None:
        gr.sync_block.__init__(
            self,
            name="sync_burst_flywheel_rx",
            in_sig=[np.complex64],
            out_sig=[np.complex64],
        )
        self._controller = SyncBurstRxController(
            sync_timing_key,
            sync_pn_key,
            session_id,
            sample_rate_hz,
            session_duration_s=session_duration_s,
            n_bursts=n_bursts,
            mean_interval_s=mean_interval_s,
            pareto_alpha=pareto_alpha,
            min_interval_s=min_interval_s,
        )
        self._last_published_index = -2

        self.message_port_register_in(pmt.intern("detect"))
        self.message_port_register_out(pmt.intern("target"))
        self.set_msg_handler(pmt.intern("detect"), self._on_detect)

    @property
    def controller(self) -> SyncBurstRxController:
        return self._controller

    def _publish_target(self, target: Optional[FlywheelTarget]) -> None:
        if target is None:
            return
        if target.epoch_index == self._last_published_index:
            return
        self._last_published_index = target.epoch_index
        msg = flywheel_target_to_pmt(
            target,
            in_search_window=self._controller.in_search_window(),
            amplitude_scale=self._controller.current_amplitude_scale(),
        )
        self.message_port_pub(pmt.intern("target"), msg)

    def _on_detect(self, msg: Any) -> None:
        ts_ms = pmt_to_detection_ms(
            msg,
            sample_rate_hz=self._controller._sample_rate_hz,
            sample_offset=self._controller.samples_processed,
        )
        if ts_ms is None:
            return
        target = self._controller.notify_burst_detected(timestamp_ms=ts_ms)
        self._publish_target(target)

    def start(self) -> bool:
        result = super().start()
        if result:
            self._last_published_index = -2
            self._publish_target(self._controller.current_target())
        return result

    def work(self, input_items: list, output_items: list) -> int:
        n = len(input_items[0])
        output_items[0][:] = input_items[0]
        before = self._controller.current_target()
        after = self._controller.tick_samples(n)
        if after is not None and (
            before is None or after.epoch_index != before.epoch_index
        ):
            self._publish_target(after)
        return n
