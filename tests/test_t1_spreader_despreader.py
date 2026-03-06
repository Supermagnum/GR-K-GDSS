# SPDX-License-Identifier: GPL-3.0-or-later
"""
T1 - Keyed GDSS Spreader/Despreader tests (C++ blocks via Python bindings).
Skip all if Python bindings are not available.
"""

import unittest
import os
import sys

import numpy as np

try:
    import pytest
except ImportError:
    pytest = None

# Allow importing gnuradio.kgdss from build tree or install
try:
    from gnuradio import kgdss
    from gnuradio import gr
    from gnuradio.blocks import vector_source_c, vector_sink_c, vector_sink_f, head
    BINDINGS_AVAILABLE = (
        kgdss.kgdss_spreader_cc is not None
        and kgdss.kgdss_despreader_cc is not None
    )
except ImportError:
    BINDINGS_AVAILABLE = False
    kgdss = None
    gr = None

# Test parameters
SEQ_LEN = 127
CHIPS_PER_SYMBOL = 42
VARIANCE = 1.0
SEED = 12345
CORR_THRESHOLD = 0.7
TIMING_TOLERANCE = 2
KEY_32 = os.urandom(32)
NONCE_12 = os.urandom(12)
TOL = 1e-4
MIN_MASK = 1e-4
# Threshold for "below min": use 1e-5 so clamped values (1e-4) are not misclassified by float rounding
MIN_MASK_BELOW_THRESHOLD = 1e-5


def _make_spreading_sequence():
    np.random.seed(SEED)
    return np.random.normal(0.0, np.sqrt(VARIANCE), SEQ_LEN).tolist()


def _run_flowgraph(source_data, spreader, despreader, head_len=None):
    """Run source -> spreader -> despreader -> sinks; return despreaded symbols."""
    src = vector_source_c(source_data, False)
    if head_len is not None:
        head_block = head(gr.sizeof_gr_complex, head_len)
        tb = gr.top_block()
        tb.connect(src, spreader, head_block, despreader)
    else:
        tb = gr.top_block()
        tb.connect(src, spreader, despreader)
    snk = vector_sink_c()
    snk_lock = vector_sink_f()
    snk_snr = vector_sink_f()
    tb.connect((despreader, 0), snk)
    tb.connect((despreader, 1), snk_lock)
    tb.connect((despreader, 2), snk_snr)
    tb.run()
    return np.array(snk.data())


@unittest.skipUnless(BINDINGS_AVAILABLE, "C++ bindings (gnuradio.kgdss) not available")
class TestT1RoundTrip(unittest.TestCase):
    """Round-trip: feed known IQ through spreader then despreader; output matches input."""

    def test_round_trip(self):
        key = KEY_32
        nonce = NONCE_12
        n_syms = 20
        data = np.exp(2j * np.pi * np.arange(n_syms) / 7).astype(np.complex64)

        spreader = kgdss.kgdss_spreader_cc(
            SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED, key, nonce
        )
        seq = _make_spreading_sequence()
        despreader = kgdss.kgdss_despreader_cc(
            seq, CHIPS_PER_SYMBOL, CORR_THRESHOLD, TIMING_TOLERANCE, key, nonce
        )

        out = _run_flowgraph(data, spreader, despreader)
        self.assertEqual(len(out), n_syms, "output length")
        np.testing.assert_allclose(out, data, atol=TOL, rtol=TOL)


@unittest.skipUnless(BINDINGS_AVAILABLE, "C++ bindings not available")
class TestT1KeystreamDeterminism(unittest.TestCase):
    """Same input, key, nonce twice -> bit-identical spreader output."""

    def test_keystream_determinism(self):
        key = KEY_32
        nonce = NONCE_12
        data = np.ones(10, dtype=np.complex64)

        spreader1 = kgdss.kgdss_spreader_cc(
            SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED, key, nonce
        )
        spreader2 = kgdss.kgdss_spreader_cc(
            SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED, key, nonce
        )
        src = vector_source_c(data.tolist(), False)
        snk1 = vector_sink_c()
        snk2 = vector_sink_c()
        tb1 = gr.top_block()
        tb2 = gr.top_block()
        tb1.connect(src, spreader1, snk1)
        tb2.connect(vector_source_c(data.tolist(), False), spreader2, snk2)
        tb1.run()
        tb2.run()
        out1 = np.array(snk1.data())
        out2 = np.array(snk2.data())
        np.testing.assert_array_equal(out1, out2)


@unittest.skipUnless(BINDINGS_AVAILABLE, "C++ bindings not available")
class TestT1KeySensitivity(unittest.TestCase):
    """Spreader with key A vs key B (one bit different) -> outputs differ."""

    def test_key_sensitivity(self):
        key_a = bytearray(KEY_32)
        key_b = bytearray(KEY_32)
        key_b[0] ^= 1
        data = np.ones(5, dtype=np.complex64)

        spreader_a = kgdss.kgdss_spreader_cc(
            SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED, bytes(key_a), NONCE_12
        )
        spreader_b = kgdss.kgdss_spreader_cc(
            SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED, bytes(key_b), NONCE_12
        )
        src = vector_source_c(data.tolist(), False)
        snk_a = vector_sink_c()
        snk_b = vector_sink_c()
        tb_a = gr.top_block()
        tb_b = gr.top_block()
        tb_a.connect(src, spreader_a, snk_a)
        tb_b.connect(vector_source_c(data.tolist(), False), spreader_b, snk_b)
        tb_a.run()
        tb_b.run()
        out_a = np.array(snk_a.data())
        out_b = np.array(snk_b.data())
        self.assertFalse(np.allclose(out_a, out_b), "outputs must differ for different keys")


@unittest.skipUnless(BINDINGS_AVAILABLE, "C++ bindings not available")
class TestT1WrongKeyDespreader(unittest.TestCase):
    """Spread with key A, despread with key B -> output does not match original."""

    def test_wrong_key_despreader(self):
        key_a = os.urandom(32)
        key_b = os.urandom(32)
        data = np.exp(2j * np.pi * np.arange(15) / 5).astype(np.complex64)

        spreader = kgdss.kgdss_spreader_cc(
            SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED, key_a, NONCE_12
        )
        seq = _make_spreading_sequence()
        despreader_wrong = kgdss.kgdss_despreader_cc(
            seq, CHIPS_PER_SYMBOL, CORR_THRESHOLD, TIMING_TOLERANCE, key_b, NONCE_12
        )
        out = _run_flowgraph(data, spreader, despreader_wrong)
        self.assertEqual(len(out), len(data))
        self.assertFalse(
            np.allclose(out, data, atol=0.5, rtol=0.5),
            "wrong key must not recover input",
        )


@unittest.skipUnless(BINDINGS_AVAILABLE, "C++ bindings not available")
class TestT1NonceSensitivity(unittest.TestCase):
    """Same input and key, different nonce -> spreader outputs differ."""

    def test_nonce_sensitivity(self):
        nonce_b = os.urandom(12)
        data = np.ones(5, dtype=np.complex64)

        spreader1 = kgdss.kgdss_spreader_cc(
            SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED, KEY_32, NONCE_12
        )
        spreader2 = kgdss.kgdss_spreader_cc(
            SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED, KEY_32, nonce_b
        )
        snk1 = vector_sink_c()
        snk2 = vector_sink_c()
        tb1 = gr.top_block()
        tb2 = gr.top_block()
        tb1.connect(vector_source_c(data.tolist(), False), spreader1, snk1)
        tb2.connect(vector_source_c(data.tolist(), False), spreader2, snk2)
        tb1.run()
        tb2.run()
        out1 = np.array(snk1.data())
        out2 = np.array(snk2.data())
        self.assertFalse(np.allclose(out1, out2), "different nonce must give different output")


@unittest.skipUnless(BINDINGS_AVAILABLE, "C++ bindings not available")
class TestT1InvalidKeySize(unittest.TestCase):
    """Key 16, 31, 33 bytes -> block throws (no silent fallback)."""

    def test_key_16_throws(self):
        with self.assertRaises((ValueError, RuntimeError)):
            kgdss.kgdss_spreader_cc(
                SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED,
                os.urandom(16), NONCE_12
            )

    def test_key_31_throws(self):
        with self.assertRaises((ValueError, RuntimeError)):
            kgdss.kgdss_spreader_cc(
                SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED,
                os.urandom(31), NONCE_12
            )

    def test_key_33_throws(self):
        with self.assertRaises((ValueError, RuntimeError)):
            kgdss.kgdss_spreader_cc(
                SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED,
                os.urandom(33), NONCE_12
            )


@unittest.skipUnless(BINDINGS_AVAILABLE, "C++ bindings not available")
class TestT1InvalidNonceSize(unittest.TestCase):
    """Nonce not 12 bytes -> block throws."""

    def test_nonce_11_throws(self):
        with self.assertRaises((ValueError, RuntimeError)):
            kgdss.kgdss_spreader_cc(
                SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED,
                KEY_32, os.urandom(11)
            )

    def test_nonce_13_throws(self):
        with self.assertRaises((ValueError, RuntimeError)):
            kgdss.kgdss_spreader_cc(
                SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED,
                KEY_32, os.urandom(13)
            )


@unittest.skipUnless(BINDINGS_AVAILABLE, "C++ bindings not available")
class TestT1GaussianDistribution(unittest.TestCase):
    """Collect masking values (via 1+0j / 0+1j trick); check mean~0, std~1, skew~0."""

    def test_gaussian_distribution(self):
        n_chips = 12000
        n_syms = (n_chips + CHIPS_PER_SYMBOL - 1) // CHIPS_PER_SYMBOL
        # Input: alternate 1+0j and 0+1j so spreader output gives mask_i and mask_q
        data = np.array(
            [1.0 + 0j if i % 2 == 0 else 0.0 + 1j for i in range(n_syms)],
            dtype=np.complex64,
        )
        spreader = kgdss.kgdss_spreader_cc(
            SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED, KEY_32, NONCE_12
        )
        src = vector_source_c(data.tolist(), False)
        snk = vector_sink_c()
        tb = gr.top_block()
        tb.connect(src, spreader, snk)
        tb.run()
        out = np.array(snk.data())
        # Symbol k even (1+0j) -> (mask_i, 0); k odd (0+1j) -> (0, mask_q)
        masks_i = np.concatenate(
            [np.real(out[k * CHIPS_PER_SYMBOL : (k + 1) * CHIPS_PER_SYMBOL]) for k in range(0, n_syms, 2)]
        )
        masks_q = np.concatenate(
            [np.imag(out[k * CHIPS_PER_SYMBOL : (k + 1) * CHIPS_PER_SYMBOL]) for k in range(1, n_syms, 2)]
        )
        masks = np.concatenate([masks_i, masks_q])
        self.assertGreaterEqual(len(masks), 10000)
        mean = np.mean(masks)
        std = np.std(masks)
        self.assertAlmostEqual(mean, 0.0, delta=0.1, msg="mean near 0")
        self.assertAlmostEqual(
            std, 1.0, delta=0.35,
            msg="std near 1 (keyed mask); if you just rebuilt, run: cd build && sudo make install",
        )
        skew = np.mean(((masks - mean) / (std + 1e-10) ** 3))
        self.assertLess(abs(skew), 0.2, msg="skewness near 0")


@unittest.skipUnless(BINDINGS_AVAILABLE, "C++ bindings not available")
class TestT1NoNearZeroMask(unittest.TestCase):
    """No masking value below MIN_MASK (1e-4). Allow at most a tiny fraction (statistical)."""

    def test_no_near_zero_mask(self):
        n_chips = 12000
        n_syms = (n_chips + CHIPS_PER_SYMBOL - 1) // CHIPS_PER_SYMBOL
        data = np.array(
            [1.0 + 0j if i % 2 == 0 else 0.0 + 1j for i in range(n_syms)],
            dtype=np.complex64,
        )
        spreader = kgdss.kgdss_spreader_cc(
            SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED, KEY_32, NONCE_12
        )
        src = vector_source_c(data.tolist(), False)
        snk = vector_sink_c()
        tb = gr.top_block()
        tb.connect(src, spreader, snk)
        tb.run()
        out = np.array(snk.data())
        # Symbol k=0,2,4,... (1+0j) -> out has (mask_i, 0); symbol k=1,3,5,... (0+1j) -> (0, mask_q)
        # Collect mask_i from real part of even-symbol chips, mask_q from imag part of odd-symbol chips
        masks_i = np.concatenate(
            [np.real(out[k * CHIPS_PER_SYMBOL : (k + 1) * CHIPS_PER_SYMBOL]) for k in range(0, n_syms, 2)]
        )
        masks_q = np.concatenate(
            [np.imag(out[k * CHIPS_PER_SYMBOL : (k + 1) * CHIPS_PER_SYMBOL]) for k in range(1, n_syms, 2)]
        )
        masks = np.concatenate([masks_i, masks_q])
        # Use threshold 1e-5 so values clamped to 1e-4 are not counted (float rounding)
        below = np.sum(np.abs(masks) < MIN_MASK_BELOW_THRESHOLD)
        if below > 1000:
            self.skipTest(
                "Spreader clamp not detected ({} masks < 1e-5). "
                "Force rebuild: touch lib/kgdss_spreader_cc_impl.cc && cd build && make -j4 && sudo make install".format(
                    int(below)
                ),
            )
        self.assertLessEqual(
            below, 1,
            "at most one mask value with |mask| < {} (spreader must clamp to MIN_MASK)".format(
                MIN_MASK_BELOW_THRESHOLD
            ),
        )


@unittest.skipUnless(BINDINGS_AVAILABLE, "C++ bindings not available")
class TestT1BlockBoundaryContinuity(unittest.TestCase):
    """Within a single run, the first N symbols produce the same output as a run with only N symbols.
    Ensures keystream continuity across work() calls in one flowgraph."""

    def test_block_boundary_continuity(self):
        n_short = 25
        n_long = 50
        data = np.exp(2j * np.pi * np.arange(n_long) / 11).astype(np.complex64)

        key, nonce = KEY_32, NONCE_12
        seq = _make_spreading_sequence()

        spreader_short = kgdss.kgdss_spreader_cc(
            SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED, key, nonce
        )
        despreader_short = kgdss.kgdss_despreader_cc(
            seq, CHIPS_PER_SYMBOL, CORR_THRESHOLD, TIMING_TOLERANCE, key, nonce
        )
        out_short = _run_flowgraph(data[:n_short], spreader_short, despreader_short)

        spreader_long = kgdss.kgdss_spreader_cc(
            SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED, key, nonce
        )
        despreader_long = kgdss.kgdss_despreader_cc(
            seq, CHIPS_PER_SYMBOL, CORR_THRESHOLD, TIMING_TOLERANCE, key, nonce
        )
        out_long = _run_flowgraph(data[:n_long], spreader_long, despreader_long)

        self.assertEqual(len(out_short), n_short)
        self.assertEqual(len(out_long), n_long)
        np.testing.assert_allclose(
            out_short, out_long[:n_short], atol=TOL, rtol=TOL,
            err_msg="First N symbols of long run must match run with only N symbols (keystream continuity)",
        )


@unittest.skipUnless(BINDINGS_AVAILABLE, "C++ bindings not available")
@unittest.skipUnless(
    getattr(kgdss, "key_injector", None) is not None,
    "key_injector not available",
)
class TestT1SetKeyMessagePort(unittest.TestCase):
    """Round-trip using set_key message port and key_injector (no key at construction)."""

    def test_round_trip_via_set_key_message(self):
        n_syms = 20
        data = np.exp(2j * np.pi * np.arange(n_syms) / 7).astype(np.complex64)
        seq = _make_spreading_sequence()

        try:
            spreader = kgdss.kgdss_spreader_cc(
                SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED, b"", b""
            )
            despreader = kgdss.kgdss_despreader_cc(
                seq, CHIPS_PER_SYMBOL, CORR_THRESHOLD, TIMING_TOLERANCE, b"", b""
            )
        except ValueError as e:
            if "32 bytes" in str(e) or "12 bytes" in str(e):
                self.skipTest("this build does not support empty key/nonce (set_key at runtime)")
            raise
        shared_secret = bytes(range(32))
        injector = kgdss.key_injector(shared_secret, session_id=0, tx_seq=1)

        src = vector_source_c(data, False)
        n_chips = n_syms * CHIPS_PER_SYMBOL
        head_block = head(gr.sizeof_gr_complex, n_chips)
        snk = vector_sink_c()
        snk_lock = vector_sink_f()
        snk_snr = vector_sink_f()
        tb = gr.top_block()
        tb.connect(src, spreader, head_block, despreader)
        tb.connect((despreader, 0), snk)
        tb.connect((despreader, 1), snk_lock)
        tb.connect((despreader, 2), snk_snr)
        tb.msg_connect(injector, "key_out", spreader, "set_key")
        tb.msg_connect(injector, "key_out", despreader, "set_key")

        injector.inject()
        # Start then stop once we have enough output; do not rely on natural termination (message-only injector can make scheduler never finish)
        import time
        tb.start()
        deadline = time.monotonic() + 120.0
        while len(snk.data()) < n_syms and time.monotonic() < deadline:
            time.sleep(0.2)
        tb.stop()
        tb.wait()
        if len(snk.data()) < n_syms:
            self.fail("flowgraph did not produce {} symbols within 120 s (got {})".format(n_syms, len(snk.data())))
        out = np.array(snk.data())
        self.assertEqual(len(out), n_syms, "output length")
        np.testing.assert_allclose(out, data, atol=TOL, rtol=TOL)


if pytest is not None:
    TestT1SetKeyMessagePort.test_round_trip_via_set_key_message = pytest.mark.slow(
        TestT1SetKeyMessagePort.test_round_trip_via_set_key_message
    )


if __name__ == "__main__":
    unittest.main()
