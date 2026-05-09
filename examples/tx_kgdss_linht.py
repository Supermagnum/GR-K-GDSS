#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: KGDSS LinHT TX (placeholder)
# Author: gr-k-gdss
# Copyright: None
# Description: Placeholder title; use tx_kgdss_linht.py comments and tx_example_kgdss.grc as the real baseline until the full QT graph is duplicated.
# GNU Radio version: v3.11.0.0git-1032-gab049f6e
#
# LinHT ZMQ (edit generated code or duplicate tx_example_kgdss into this GRC):
#   TX IQ PUB: ipc:///tmp/linht_tx or tcp://0.0.0.0:17101 (zeromq.pub_sink, bind=True)
#   PTT SUB:  gnuradio.kgdss.LinhtPttMsgSource("ipc:///tmp/linht_ptt") -> msg_connect ptt -> spreader
#   Centre frequency (e.g. 433.5e6): configured on the Lin HT / daemon side for UHF.

from PyQt5 import Qt
from gnuradio import qtgui
import threading
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation




class tx_kgdss_linht(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "KGDSS LinHT TX (placeholder)", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("KGDSS LinHT TX (placeholder)")
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

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "tx_kgdss_linht")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()




    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "tx_kgdss_linht")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()




def main(top_block_cls=tx_kgdss_linht, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()


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
