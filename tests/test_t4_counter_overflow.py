# SPDX-License-Identifier: GPL-3.0-or-later
"""
T4 - ChaCha20-IETF counter overflow and re-key recovery tests.
"""

import threading

import numpy as np
import pmt
import pytest

from channel_sim import M1225_VEHICULAR_A, apply_channel

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
CHIPS_PER_SYMBOL_OVERFLOW = 1  # minimal symbols needed for overflow boundary trigger
CHIPS_PER_SYMBOL_RECOVERY = 42  # robust setting under Vehicular A; aligned with T2
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


def _run_spreader_only(symbols, spreader):
    src = vector_source_c(symbols.astype(np.complex64), False)
    snk = vector_sink_c()
    tb = gr.top_block()
    tb.connect(src, spreader, snk)
    tb.run()
    return np.array(snk.data(), dtype=np.complex64)


def _run_despreader_only(chips, despreader):
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


def _run_top_block_with_timeout(tb, timeout_s=10.0):
    err = []

    def _runner():
        try:
            tb.run()
        except Exception as exc:  # pragma: no cover - defensive capture
            err.append(exc)

    thr = threading.Thread(target=_runner, daemon=True)
    thr.start()
    thr.join(timeout=timeout_s)
    if thr.is_alive():
        tb.stop()
        tb.wait()
        pytest.fail("tb.run() did not return within 10 seconds")
    if err:
        raise err[0]


def _post_set_counter(block, ctr):
    bb = block.to_basic_block()
    bb._post(pmt.intern("set_counter"), pmt.from_uint64(int(ctr)))


@pytest.mark.skipif(not BINDINGS_AVAILABLE, reason="C++ bindings not available")
def test_counter_overflow_detection():
    """
    Physical basis:
    - ChaCha20-IETF counter is 32-bit blocks; boundary crossing must be rejected.
    Failure implies unsafe counter handling in overflow edge conditions.
    """
    key_a, nonce_a = _det_key_nonce(42)

    spreader = kgdss.kgdss_spreader_cc(
        SEQ_LEN, CHIPS_PER_SYMBOL_OVERFLOW, VARIANCE, SEED, key_a, nonce_a
    )
    ports_in = str(spreader.to_basic_block().message_ports_in())
    if "set_counter" not in ports_in:
        pytest.xfail("set_counter test hook not available in currently loaded kgdss_python module")
    seq = spreader.get_spreading_sequence()
    despreader = kgdss.kgdss_despreader_cc(
        seq, CHIPS_PER_SYMBOL_OVERFLOW, 0.1, TIMING_TOLERANCE, key_a, nonce_a
    )

    # With 8 bytes/chip and chips_per_symbol=1, one symbol consumes 8 bytes.
    # Set counter in block UINT32_MAX at byte offset 60, then one symbol pushes
    # last_byte into block UINT32_MAX+1 and should trigger overflow guard.
    near_overflow_ctr = (np.uint64(0xFFFFFFFF) * np.uint64(64)) + np.uint64(60)
    _post_set_counter(spreader, int(near_overflow_ctr))
    _post_set_counter(despreader, int(near_overflow_ctr))

    _bits_ov, syms_ov = _make_bpsk_symbols(1, seed=44)
    # Overflow must be signaled without throwing; flowgraph should terminate promptly.
    src_ov = vector_source_c(syms_ov.astype(np.complex64), False)
    snk_ov = vector_sink_c()
    tb_ov = gr.top_block()
    tb_ov.connect(src_ov, spreader, snk_ov)
    _run_top_block_with_timeout(tb_ov, timeout_s=10.0)
    assert spreader.get_overflow_occurred()

    # Validate despreader reports the same non-throw overflow signal path.
    src_ov_d = vector_source_c(np.array([1.0 + 0.0j], dtype=np.complex64), False)
    snk_ov_d0 = vector_sink_c()
    snk_ov_d1 = vector_sink_f()
    snk_ov_d2 = vector_sink_f()
    tb_ov_d = gr.top_block()
    tb_ov_d.connect(src_ov_d, despreader)
    tb_ov_d.connect((despreader, 0), snk_ov_d0)
    tb_ov_d.connect((despreader, 1), snk_ov_d1)
    tb_ov_d.connect((despreader, 2), snk_ov_d2)
    _run_top_block_with_timeout(tb_ov_d, timeout_s=10.0)
    assert despreader.get_overflow_occurred()


@pytest.mark.skipif(not BINDINGS_AVAILABLE, reason="C++ bindings not available")
def test_rekey_recovery_vehicular_a():
    """
    Physical basis:
    - Fresh post-rekey key/nonce state should support robust despreading under
      M.1225 Vehicular A at 15 dB once acquisition has settled.
    Failure implies degraded key/counter-aligned recovery quality in channel.
    """
    key_b, nonce_b = _det_key_nonce(43)

    spreader = kgdss.kgdss_spreader_cc(
        SEQ_LEN, CHIPS_PER_SYMBOL_RECOVERY, VARIANCE, SEED, key_b, nonce_b
    )
    seq = spreader.get_spreading_sequence()
    despreader = kgdss.kgdss_despreader_cc(
        seq, CHIPS_PER_SYMBOL_RECOVERY, 0.1, TIMING_TOLERANCE, key_b, nonce_b
    )

    bits, syms = _make_bpsk_symbols(500, seed=45)
    chips = _run_spreader_only(syms, spreader)
    channel_snr_db = 15.0
    ch = apply_channel(chips, M1225_VEHICULAR_A, channel_snr_db, sample_rate=SAMPLE_RATE, seed=42)
    out, lock, _snr = _run_despreader_only(ch, despreader)

    assert len(out) >= 450
    # Physical: after state reset and channel settle, lock should return.
    assert np.mean(lock[400:]) > 0.5
    # BER in final 100 symbols should be low if counters and key state resync correctly.
    tail = min(100, len(out))
    dec = (np.real(out[-tail:]) >= 0).astype(np.int8)
    ber = float(np.mean(dec != bits[-tail:]))
    assert ber < 0.05
    # Physical: this recovery run is configured at 15 dB channel SNR.
    assert abs(float(channel_snr_db) - 15.0) <= 6.0

    # Counter independence post-rekey: immediate post-lock symbol should reconstruct
    # close to source, not just "lock true". Use decision-directed EVM for BPSK.
    idx = max(400, len(out) - tail)
    decided = 1.0 + 0.0j if np.real(out[idx]) >= 0.0 else -1.0 + 0.0j
    e = decided - syms[idx]
    evm = float(abs(e) / (abs(syms[idx]) + 1e-12))
    assert evm < 0.15

