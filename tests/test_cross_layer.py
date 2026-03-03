# SPDX-License-Identifier: GPL-3.0-or-later
"""
Cross-layer integration: full stack round-trip.
Derive session keys from test ECDH shared secret, use gdss_masking + nonce,
run IQ through keyed spreader then despreader, verify recovered signal matches input.
"""

import unittest
import os

import numpy as np

try:
    from gnuradio import kgdss
    from gnuradio import gr
    from gnuradio.blocks import vector_source_c, vector_sink_c, vector_sink_f
    from gnuradio.kgdss import derive_session_keys, gdss_nonce
    BINDINGS_AVAILABLE = (
        kgdss.kgdss_spreader_cc is not None
        and kgdss.kgdss_despreader_cc is not None
    )
    T3_AVAILABLE = derive_session_keys is not None and gdss_nonce is not None
except ImportError:
    BINDINGS_AVAILABLE = False
    T3_AVAILABLE = False
    kgdss = None
    gr = None

SEQ_LEN = 127
CHIPS_PER_SYMBOL = 42
VARIANCE = 1.0
SEED = 999
CORR_THRESHOLD = 0.7
TIMING_TOLERANCE = 2
TOL = 1e-3


@unittest.skipUnless(
    BINDINGS_AVAILABLE and T3_AVAILABLE,
    "C++ bindings and session_key_derivation required",
)
class TestCrossLayerFullStackRoundTrip(unittest.TestCase):
    """Derive keys from shared secret, spread then despread with keyed blocks, match input."""

    def test_full_stack_round_trip(self):
        ecdh_shared_secret = os.urandom(32)
        keys = derive_session_keys(ecdh_shared_secret)
        gdss_key = keys["gdss_masking"]
        self.assertEqual(len(gdss_key), 32)

        session_id = 1
        tx_seq = 0
        nonce = gdss_nonce(session_id, tx_seq)
        self.assertEqual(len(nonce), 12)

        n_syms = 30
        data = np.exp(2j * np.pi * np.arange(n_syms) / 7).astype(np.complex64)

        spreader = kgdss.kgdss_spreader_cc(
            SEQ_LEN, CHIPS_PER_SYMBOL, VARIANCE, SEED,
            gdss_key, nonce
        )
        np.random.seed(SEED)
        spreading_sequence = np.random.normal(
            0.0, np.sqrt(VARIANCE), SEQ_LEN
        ).tolist()
        despreader = kgdss.kgdss_despreader_cc(
            spreading_sequence,
            CHIPS_PER_SYMBOL,
            CORR_THRESHOLD,
            TIMING_TOLERANCE,
            gdss_key,
            nonce,
        )

        src = vector_source_c(data.tolist(), False)
        snk = vector_sink_c()
        snk_lock = vector_sink_f()
        snk_snr = vector_sink_f()
        tb = gr.top_block()
        tb.connect(src, spreader, despreader)
        tb.connect((despreader, 0), snk)
        tb.connect((despreader, 1), snk_lock)
        tb.connect((despreader, 2), snk_snr)
        tb.run()

        out = np.array(snk.data())
        self.assertEqual(len(out), n_syms)
        np.testing.assert_allclose(out, data, atol=TOL, rtol=TOL)


if __name__ == "__main__":
    unittest.main()
