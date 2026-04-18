# SPDX-License-Identifier: GPL-3.0-or-later
"""
T5 - ITU-R M.1225 Pedestrian B strict timing capability tests.

Pedestrian B at 1 Msps exercises the adaptive timing loop, matched-filter
despreading, and decision-directed channel equalization. These thresholds are
empirical capability boundaries for this implementation.
"""

import numpy as np
import pytest

from channel_sim import M1225_PEDESTRIAN_B, apply_channel, apply_chip_timing_offset, make_delay_sweep_profile

try:
    from gnuradio import kgdss
    from gnuradio import gr
    from gnuradio.blocks import vector_source_c, vector_sink_c, vector_sink_f
    BINDINGS_AVAILABLE = (
        kgdss.kgdss_spreader_cc is not None
        and kgdss.kgdss_despreader_cc is not None
    )
except ImportError:
    BINDINGS_AVAILABLE = False
    kgdss = None
    gr = None


SEQ_LEN = 127
CHIPS_PER_SYMBOL = 42
VARIANCE = 1.0
SEED = 12345
TIMING_TOLERANCE = 3
SAMPLE_RATE = 1_000_000.0


def _det_key_nonce(seed=42):
    rng = np.random.default_rng(seed)
    key = rng.integers(0, 256, size=32, dtype=np.uint8).tobytes()
    nonce = rng.integers(0, 256, size=12, dtype=np.uint8).tobytes()
    return key, nonce


def _make_bpsk_symbols(n_syms, seed=42):
    rng = np.random.default_rng(seed)
    bits = rng.integers(0, 2, size=n_syms, dtype=np.int8)
    syms = np.where(bits == 0, -1.0, 1.0).astype(np.float32)
    return bits.astype(np.int8), syms.astype(np.complex64)


def _run_spreader_only(symbols, key, nonce):
    spreader = kgdss.kgdss_spreader_cc(
        SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED, key, nonce
    )
    src = vector_source_c(symbols.astype(np.complex64), False)
    snk = vector_sink_c()
    tb = gr.top_block()
    tb.connect(src, spreader, snk)
    tb.run()
    return np.array(snk.data(), dtype=np.complex64), spreader.get_spreading_sequence()


def _run_despreader_only(chips, seq, key, nonce, corr_threshold=0.1):
    despreader = kgdss.kgdss_despreader_cc(
        seq, CHIPS_PER_SYMBOL, corr_threshold, TIMING_TOLERANCE, key, nonce
    )
    # T5 uses BPSK data under fading; enable decision-directed channel
    # equalization to recover amplitude and phase of the effective channel gain.
    despreader.set_channel_equalization(True)
    src = vector_source_c(chips.astype(np.complex64), False)
    snk = vector_sink_c()
    snk_lock = vector_sink_f()
    snk_snr = vector_sink_f()
    tb = gr.top_block()
    tb.connect(src, despreader)
    tb.connect((despreader, 0), snk)
    tb.connect((despreader, 1), snk_lock)
    tb.connect((despreader, 2), snk_snr)
    tb.run()
    out = np.array(snk.data(), dtype=np.complex64)
    lock = np.array(snk_lock.data(), dtype=np.float32)
    snr = np.array(snk_snr.data(), dtype=np.float32)
    return out, lock, snr


def _evm(out_syms, ref_syms):
    e = out_syms - ref_syms[: len(out_syms)]
    ref_rms = np.sqrt(np.mean(np.abs(ref_syms[: len(out_syms)]) ** 2) + 1e-12)
    return float(np.sqrt(np.mean(np.abs(e) ** 2)) / ref_rms)


@pytest.mark.skipif(not BINDINGS_AVAILABLE, reason="C++ bindings not available")
@pytest.mark.parametrize("snr_db", [10, 15, 20])
def test_pedestrian_b_convergence(snr_db):
    """
    ITU-R M.1225 Pedestrian B (max 3700 ns delay -> 3.7 samples at 1 Msps).
    Physical pass condition: after warmup, residual timing/multipath error is bounded
    in symbol quality (EVM) and lock confidence at moderate/high SNR.
    """
    key, nonce = _det_key_nonce(42)
    _bits, syms = _make_bpsk_symbols(1400, seed=43)
    chips, seq = _run_spreader_only(syms, key, nonce)
    ch = apply_channel(chips, M1225_PEDESTRIAN_B, snr_db, sample_rate=SAMPLE_RATE, seed=78)
    out, lock, _snr = _run_despreader_only(ch, seq, key, nonce, corr_threshold=0.1)

    warmup = 1000
    tail = out[warmup: warmup + 200]
    ref = syms[warmup: warmup + 200]
    evm = _evm(tail, ref)

    if snr_db >= 15:
        assert evm < 0.25
        assert np.mean(lock[warmup: warmup + 200]) > 0.5
    else:
        assert evm < 0.40

    # Stability proxy for timing convergence: lock metric in last window should
    # not fluctuate wildly if timing settles.
    assert float(np.std(lock[warmup + 150: warmup + 200])) < 1.0


@pytest.mark.skipif(not BINDINGS_AVAILABLE, reason="C++ bindings not available")
@pytest.mark.parametrize(
    "max_delay_chips",
    [
        1,
        2,
        3,
        pytest.param(4, marks=pytest.mark.xfail(reason="timing_error_tolerance exceeded, known limitation")),
        pytest.param(5, marks=pytest.mark.xfail(reason="timing_error_tolerance exceeded, known limitation")),
    ],
)
def test_pedestrian_b_delay_spread_boundary(max_delay_chips):
    """
    Boundary sweep over max tap delay (1..5 chips) at fixed SNR=15 dB.
    Physical pass condition: implementation should hold bounded EVM up to its
    practical timing tolerance boundary.
    """
    key, nonce = _det_key_nonce(52 + max_delay_chips)
    _bits, syms = _make_bpsk_symbols(1200, seed=53 + max_delay_chips)
    chips, seq = _run_spreader_only(syms, key, nonce)
    model = make_delay_sweep_profile(max_delay_ns=1000.0 * max_delay_chips, speed_kmh=3.0, n_taps=6)
    ch = apply_channel(chips, model, 15, sample_rate=SAMPLE_RATE, seed=78)
    out, lock, _snr = _run_despreader_only(ch, seq, key, nonce, corr_threshold=0.1)

    warmup = 800
    evm = _evm(out[warmup:warmup + 200], syms[warmup:warmup + 200])
    assert evm < 0.35
    assert np.mean(lock[warmup:warmup + 200]) > 0.3


@pytest.mark.skipif(not BINDINGS_AVAILABLE, reason="C++ bindings not available")
@pytest.mark.parametrize("offset_chips", [0, 1, -1, 2, -2])
def test_pedestrian_b_timing_offset_tracking(offset_chips):
    """
    Pedestrian B + injected integer timing offsets at SNR=15 dB.
    Physical pass condition: timing loop and correlator recover symbol quality
    after convergence under combined multipath+offset stress.
    """
    key, nonce = _det_key_nonce(62 + offset_chips)
    _bits, syms = _make_bpsk_symbols(900, seed=63 + offset_chips)
    chips, seq = _run_spreader_only(syms, key, nonce)
    ch = apply_channel(chips, M1225_PEDESTRIAN_B, 15, sample_rate=SAMPLE_RATE, seed=78)
    shifted = apply_chip_timing_offset(ch, offset_chips)
    out, lock, _snr = _run_despreader_only(shifted, seq, key, nonce, corr_threshold=0.1)

    conv = 300
    evm = _evm(out[conv:conv + 200], syms[conv:conv + 200])
    assert evm < 0.25
    assert np.mean(lock[conv:conv + 200]) > 0.4

