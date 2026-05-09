#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: KGDSS LinHT-style ZMQ loopback
# Author: gr-k-gdss
# Copyright: None
# Description: Minimal keyed GDSS ZMQ loopback at 500 ksps (AWGN). Keys are demo hex; replace for real use.
# GNU Radio version: v3.11.0.0git-1032-gab049f6e
#
# LinHT / TCP: PUB bind tcp://127.0.0.1:17101; SUB connect same URL (loopback).
# On hardware: use ipc:///tmp/linht_tx and ipc:///tmp/linht_rx with the daemon.

from gnuradio import analog
from gnuradio import blocks
from gnuradio import kgdss
import binascii
import numpy as np
from gnuradio import zeromq
import threading
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation




class loopback_kgdss_linht(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "KGDSS LinHT-style ZMQ loopback", catch_exceptions=True)

        ##################################################
        # Variables
        ##################################################
        self.linht_rate = linht_rate = 500000
        self.demo_nonce_hex = demo_nonce_hex = "000102030405060708090a0b"
        self.demo_key_hex = demo_key_hex = "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20"

        ##################################################
        # Blocks
        ##################################################

        self.zeromq_sub_source_0 = zeromq.sub_source(gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:17101", 100, False, (-1), "", False)
        self.zeromq_pub_sink_0 = zeromq.pub_sink(gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:17101", 100, False, (-1), "", True, True)
        self.kgdss_spreader_cc_0 = kgdss.kgdss_spreader_cc(
            256,
            256,
            1.0,
            1,
            list(binascii.unhexlify(demo_key_hex.strip('"')) if demo_key_hex not in ('""', '') else b''),
            list(binascii.unhexlify(demo_nonce_hex.strip('"')) if demo_nonce_hex not in ('""', '') else b''))
        self.kgdss_despreader_cc_0 = np.random.seed(1 if 1 > 0 else None)
        spreading_sequence = np.random.normal(0.0, np.sqrt(1.0), 256).tolist()

        kgdss.kgdss_despreader_cc(
            spreading_sequence,
            256,
            0.7,
            2,
            list(binascii.unhexlify(demo_key_hex.strip('"')) if demo_key_hex not in ('""', '') else b''),
            list(binascii.unhexlify(demo_nonce_hex.strip('"')) if demo_nonce_hex not in ('""', '') else b''))
        self.blocks_throttle_0 = blocks.throttle(gr.sizeof_gr_complex*1, linht_rate,True)
        self.blocks_null_sink_2 = blocks.null_sink(gr.sizeof_float*1)
        self.blocks_null_sink_1 = blocks.null_sink(gr.sizeof_float*1)
        self.blocks_null_sink_0 = blocks.null_sink(gr.sizeof_gr_complex*1)
        self.blocks_add_xx_0 = blocks.add_vcc(1)
        self.analog_noise_source_x_0 = analog.noise_source_c(analog.GR_GAUSSIAN, 1, 0)
        self.analog_const_source_x_0 = analog.sig_source_c(0, analog.GR_CONST_WAVE, 0, 0, 0)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.analog_const_source_x_0, 0), (self.blocks_throttle_0, 0))
        self.connect((self.analog_noise_source_x_0, 0), (self.blocks_add_xx_0, 1))
        self.connect((self.blocks_add_xx_0, 0), (self.kgdss_despreader_cc_0, 0))
        self.connect((self.blocks_throttle_0, 0), (self.kgdss_spreader_cc_0, 0))
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


if __name__ == '__main__':
    main()
