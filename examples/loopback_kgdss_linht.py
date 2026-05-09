#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: KGDSS LinHT-style ZMQ loopback
# Author: gr-k-gdss
# Copyright: None
# Description: Keyed GDSS ZMQ loopback at 500 ksps (AWGN). Keys from HKDF (gdss_masking + gdss_nonce); replace test secret for real use.
# GNU Radio version: v3.11.0.0git-1032-gab049f6e
#
# LinHT / TCP: PUB bind tcp://127.0.0.1:17101; SUB connect same URL (loopback).
# On hardware: use ipc:///tmp/linht_tx and ipc:///tmp/linht_rx with the daemon.

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PYDIR = os.path.join(_REPO_ROOT, "python")
if _PYDIR not in sys.path:
    sys.path.insert(0, _PYDIR)

if __name__ == "__main__" and any(a in sys.argv for a in ("-h", "--help")):
    print(
        "usage: loopback_kgdss_linht.py [-h]\n\n"
        "Keyed GDSS ZMQ loopback at 500 ksps (HKDF gdss_masking key, TCP 127.0.0.1:17101).\n"
        "Requires: GNU Radio, gr-k-gdss (kgdss), gr-zeromq, and the Python binding pyzmq\n"
        "  (e.g. apt install python3-zmq).\n\n"
        "Run with no arguments; press Enter to stop."
    )
    sys.exit(0)

from gnuradio import analog
from gnuradio import blocks
from gnuradio import kgdss
import numpy as np
from gnuradio import zeromq
from gnuradio import gr
import signal
from session_key_derivation import derive_session_keys, gdss_nonce


def _max_complex_corr(a, b, max_lag=512):
    """Best normalized |rho| over small lags (handles ZMQ / pipeline delay)."""
    a = np.asarray(a, dtype=np.complex128).ravel()
    b = np.asarray(b, dtype=np.complex128).ravel()
    a = a - np.mean(a)
    b = b - np.mean(b)
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return float("nan")
    best = 0.0
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            aa, bb = a[lag:], b[: lb - lag] if lb > lag else b[:0]
            n = min(len(aa), len(bb))
        else:
            aa, bb = a[: la + lag], b[-lag:]
            n = min(len(aa), len(bb))
        if n < 32:
            continue
        aa, bb = aa[:n], bb[:n]
        num = abs(float(np.real(np.vdot(aa, bb))))
        den = float(np.linalg.norm(aa) * np.linalg.norm(bb)) + 1e-12
        best = max(best, num / den)
    return best


class loopback_kgdss_linht(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "KGDSS LinHT-style ZMQ loopback", catch_exceptions=True)

        ##################################################
        # Variables
        ##################################################
        self.linht_rate = linht_rate = 500000
        test_secret = bytes(range(32))
        session_label = "loopback-test-001"
        keys = derive_session_keys(test_secret)
        gdss_key = keys["gdss_masking"]
        gdss_nonce_bytes = gdss_nonce(session_label, 0)
        self.demo_key_hex = gdss_key.hex()
        self.demo_nonce_hex = gdss_nonce_bytes.hex()
        _demo_key = gdss_key
        _demo_nonce = gdss_nonce_bytes

        ##################################################
        # Spreading sequence: despreader still needs a non-empty vector for legacy
        # correlation metrics; masking for data recovery is ChaCha20 (matched to spreader).
        ##################################################
        spreading_sequence = [1.0] * 256

        ##################################################
        # Blocks
        ##################################################

        self.zeromq_sub_source_0 = zeromq.sub_source(gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:17101", 100, False, (-1), "", False)
        self.zeromq_pub_sink_0 = zeromq.pub_sink(gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:17101", 100, False, (-1), "", True, True)
        self.kgdss_spreader_cc_0 = kgdss.kgdss_spreader_cc(256, 256, 1.0, 1, _demo_key, _demo_nonce)

        self.kgdss_despreader_cc_0 = kgdss.kgdss_despreader_cc(
            spreading_sequence,
            256,
            0.7,
            2,
            _demo_key,
            _demo_nonce,
        )
        self.blocks_throttle_0 = blocks.throttle(gr.sizeof_gr_complex*1, linht_rate,True)
        self.blocks_null_sink_2 = blocks.null_sink(gr.sizeof_float*1)
        self.blocks_null_sink_1 = blocks.null_sink(gr.sizeof_float*1)
        self.blocks_null_sink_0 = blocks.null_sink(gr.sizeof_gr_complex*1)
        self.blocks_add_xx_0 = blocks.add_vcc(1)
        self.analog_noise_source_x_0 = analog.noise_source_c(analog.GR_GAUSSIAN, 0.02, 0)
        self.analog_const_source_x_0 = analog.sig_source_c(linht_rate, analog.GR_CONST_WAVE, 0, 1.0, 0)

        # Taps for end-to-end symbol correlation (same key/nonce as spread/despread).
        self._sym_tap_n = 8192
        self.blocks_head_sym_0 = blocks.head(gr.sizeof_gr_complex, self._sym_tap_n)
        self.blocks_head_ds_0 = blocks.head(gr.sizeof_gr_complex, self._sym_tap_n)
        self.blocks_vector_sink_sym_0 = blocks.vector_sink_c()
        self.blocks_vector_sink_ds_0 = blocks.vector_sink_c()

        ##################################################
        # Connections
        ##################################################
        self.connect((self.analog_const_source_x_0, 0), (self.blocks_throttle_0, 0))
        self.connect((self.blocks_throttle_0, 0), (self.kgdss_spreader_cc_0, 0))
        self.connect((self.blocks_throttle_0, 0), (self.blocks_head_sym_0, 0))
        self.connect((self.blocks_head_sym_0, 0), (self.blocks_vector_sink_sym_0, 0))
        self.connect((self.analog_noise_source_x_0, 0), (self.blocks_add_xx_0, 1))
        self.connect((self.blocks_add_xx_0, 0), (self.kgdss_despreader_cc_0, 0))
        self.connect((self.kgdss_despreader_cc_0, 0), (self.blocks_head_ds_0, 0))
        self.connect((self.blocks_head_ds_0, 0), (self.blocks_vector_sink_ds_0, 0))
        self.connect((self.kgdss_despreader_cc_0, 0), (self.blocks_null_sink_0, 0))
        self.connect((self.kgdss_despreader_cc_0, 1), (self.blocks_null_sink_1, 0))
        self.connect((self.kgdss_despreader_cc_0, 2), (self.blocks_null_sink_2, 0))
        self.connect((self.kgdss_spreader_cc_0, 0), (self.zeromq_pub_sink_0, 0))
        self.connect((self.zeromq_sub_source_0, 0), (self.blocks_add_xx_0, 0))


    def get_linht_rate(self):
        return self.linht_rate

    def set_linht_rate(self, linht_rate):
        self.linht_rate = linht_rate
        self.blocks_throttle_0.set_sample_rate(self.linht_rate)

    def get_demo_nonce_hex(self):
        return self.demo_nonce_hex

    def set_demo_nonce_hex(self, demo_nonce_hex):
        self.demo_nonce_hex = demo_nonce_hex

    def get_demo_key_hex(self):
        return self.demo_key_hex

    def set_demo_key_hex(self, demo_key_hex):
        self.demo_key_hex = demo_key_hex

    def print_symbol_correlation(self):
        sy = np.array(self.blocks_vector_sink_sym_0.data())
        ds = np.array(self.blocks_vector_sink_ds_0.data())
        rho = _max_complex_corr(sy, ds)
        n_sym = min(len(sy), len(ds))
        print(
            f"loopback: gdss_masking + gdss_nonce session label loopback-test-001; "
            f"captured min(len(sym),len(ds))={n_sym} symbols; "
            f"max lag-normalized correlation |rho|={rho:.4f}"
        )


def main(top_block_cls=loopback_kgdss_linht, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()

    try:
        input('Press Enter to quit: ')
    except EOFError:
        pass
    tb.stop()
    tb.wait()
    try:
        tb.print_symbol_correlation()
    except Exception as ex:
        print(f"loopback: correlation report skipped ({ex})")


if __name__ == '__main__':
    main()
