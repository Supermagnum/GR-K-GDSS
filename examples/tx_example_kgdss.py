#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Keyed GDSS TX Example
# Author: gr-k-gdss
# Copyright: Copyright 2024
# Description: Keyed GDSS TX example. Audio from mic -> Codec2 -> ECIES encrypt -> SOQPSK mod -> Keyed GDSS Spreader -> SDR sink. Replace Null Sink with osmocom Sink or UHD Sink for hardware output.
# GNU Radio version: v3.11.0.0git-1032-gab049f6e

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio import audio
from gnuradio import blocks
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import kgdss
import binascii
from gnuradio import linux_crypto
from gnuradio import qradiolink
from gnuradio import vocoder
from gnuradio.vocoder import codec2
import threading
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation




class tx_example_kgdss(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Keyed GDSS TX Example", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Keyed GDSS TX Example")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "tx_example_kgdss")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.tx_seq = tx_seq = 0
        self.session_id = session_id = 1
        self.sample_rate = sample_rate = 8000
        self.keyring_id = keyring_id = 1
        self.key_store_path = key_store_path = ""
        self.callsigns = callsigns = ""

        ##################################################
        # Blocks
        ##################################################

        self.vocoder_codec2_encode_sp_0 = vocoder.codec2_encode_sp(codec2.MODE_2400)
        self.rational_resampler_xxx_0 = filter.rational_resampler_fff(
                interpolation=1,
                decimation=6,
                taps=[],
                fractional_bw=0)
        self.qradiolink_mod_soqpsk_0 = qradiolink.mod_soqpsk(mode=1, sps=10, samp_rate=250000, carrier_freq=0, filter_width=10000)
        self.kgdss_spreader_cc_0 = kgdss.kgdss_spreader_cc(
            256,
            256,
            1.0,
            0,
            list(binascii.unhexlify("".strip('"')) if "" not in ('""', '') else b''),
            list(binascii.unhexlify("".strip('"')) if "" not in ('""', '') else b''))
        self.kgdss_key_injector_0 = kgdss.key_injector(keyring_id=keyring_id, session_id=session_id, tx_seq=tx_seq) if keyring_id else kgdss.key_injector(shared_secret=bytes.fromhex((str("0000000000000000000000000000000000000000000000000000000000000000").replace('"', '').strip() + '00'*32)[:64]), session_id=session_id, tx_seq=tx_seq)
        self.brainpool_ecies_multi_encrypt_0 = linux_crypto.brainpool_ecies_multi_encrypt("brainpoolP256r1", callsigns, key_store_path, "gr-linux-crypto-ecies-v1")
        self.blocks_vector_to_stream_0 = blocks.vector_to_stream(gr.sizeof_char*1, 48)
        self.blocks_unpack_k_bits_bb_0 = blocks.unpack_k_bits_bb(8)
        self.blocks_null_sink_0 = blocks.null_sink(gr.sizeof_gr_complex*1)
        self.blocks_float_to_short_0 = blocks.float_to_short(1, 32768)
        self.audio_source_0 = audio.source(48000, '', True)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.kgdss_key_injector_0, 'set_key'), (self.kgdss_spreader_cc_0, 'set_key'))
        self.connect((self.audio_source_0, 0), (self.rational_resampler_xxx_0, 0))
        self.connect((self.blocks_float_to_short_0, 0), (self.vocoder_codec2_encode_sp_0, 0))
        self.connect((self.blocks_unpack_k_bits_bb_0, 0), (self.qradiolink_mod_soqpsk_0, 0))
        self.connect((self.blocks_vector_to_stream_0, 0), (self.brainpool_ecies_multi_encrypt_0, 0))
        self.connect((self.brainpool_ecies_multi_encrypt_0, 0), (self.blocks_unpack_k_bits_bb_0, 0))
        self.connect((self.kgdss_spreader_cc_0, 0), (self.blocks_null_sink_0, 0))
        self.connect((self.qradiolink_mod_soqpsk_0, 0), (self.kgdss_spreader_cc_0, 0))
        self.connect((self.rational_resampler_xxx_0, 0), (self.blocks_float_to_short_0, 0))
        self.connect((self.vocoder_codec2_encode_sp_0, 0), (self.blocks_vector_to_stream_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "tx_example_kgdss")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_tx_seq(self):
        return self.tx_seq

    def set_tx_seq(self, tx_seq):
        self.tx_seq = tx_seq

    def get_session_id(self):
        return self.session_id

    def set_session_id(self, session_id):
        self.session_id = session_id

    def get_sample_rate(self):
        return self.sample_rate

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate

    def get_keyring_id(self):
        return self.keyring_id

    def set_keyring_id(self, keyring_id):
        self.keyring_id = keyring_id

    def get_key_store_path(self):
        return self.key_store_path

    def set_key_store_path(self, key_store_path):
        self.key_store_path = key_store_path

    def get_callsigns(self):
        return self.callsigns

    def set_callsigns(self, callsigns):
        self.callsigns = callsigns
        self.brainpool_ecies_multi_encrypt_0.set_callsigns(self.callsigns)




def main(top_block_cls=tx_example_kgdss, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
