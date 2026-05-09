# SPDX-License-Identifier: GPL-3.0-or-later
"""
LinHT ZeroMQ IPC bridge for GR-K-GDSS.

Provides a thin adapter between GR-K-GDSS flowgraphs and the LinHT daemon's ZeroMQ
PUB/SUB proxy, matching common LinHT socket layout and message formats.

LinHT ZMQ endpoints (defaults, all configurable):

  RX baseband PUB (daemon publishes IQ): ipc:///tmp/linht_rx
  TX baseband SUB (daemon consumes IQ from flowgraph): ipc:///tmp/linht_tx
  PTT events PUB (daemon publishes PTT strings): ipc:///tmp/linht_ptt
  RF events SUB (daemon consumes status strings): ipc:///tmp/linht_events

IQ sample format: interleaved complex float32 (same layout as NumPy complex64).

PTT message format on wire: UTF-8 strings ``ptt_on`` and ``ptt_off`` (LinHT convention).
"""

from __future__ import annotations

import threading
import time
from typing import Optional

try:
    import zmq
except ImportError:  # pragma: no cover - optional dependency
    zmq = None  # type: ignore

import pmt
from gnuradio import gr


class LinhtBridge:
    """Manage ZMQ sockets for LinHT IQ and side channels (optional background I/O)."""

    def __init__(
        self,
        rx_endpoint: str = "ipc:///tmp/linht_rx",
        tx_endpoint: str = "ipc:///tmp/linht_tx",
        ptt_endpoint: str = "ipc:///tmp/linht_ptt",
        events_endpoint: str = "ipc:///tmp/linht_events",
        sample_rate: float = 500_000.0,
        ptt_command_endpoint: str = "",
    ):
        if zmq is None:
            raise RuntimeError("pyzmq is required for LinhtBridge")
        self.rx_endpoint = rx_endpoint
        self.tx_endpoint = tx_endpoint
        self.ptt_endpoint = ptt_endpoint
        self.events_endpoint = events_endpoint
        self.sample_rate = float(sample_rate)
        self.ptt_command_endpoint = ptt_command_endpoint
        self._ctx: Optional[zmq.Context] = None
        self._rx_sub: Optional[zmq.Socket] = None
        self._tx_pub: Optional[zmq.Socket] = None
        self._ptt_cmd: Optional[zmq.Socket] = None
        self._events_pub: Optional[zmq.Socket] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._connected = False

    def start(self) -> None:
        """Create ZMQ context and sockets. Bracket RX/TX with LinHT daemon as appropriate."""
        if zmq is None:
            raise RuntimeError("pyzmq is required for LinhtBridge")
        self._ctx = zmq.Context.instance()
        self._rx_sub = self._ctx.socket(zmq.SUB)
        self._rx_sub.setsockopt(zmq.SUBSCRIBE, b"")
        self._rx_sub.connect(self.rx_endpoint)
        self._tx_pub = self._ctx.socket(zmq.PUB)
        try:
            self._tx_pub.bind(self.tx_endpoint.replace("tcp://*", "tcp://0.0.0.0"))
        except zmq.ZMQError:
            self._tx_pub.connect(self.tx_endpoint)
        self._events_pub = self._ctx.socket(zmq.PUB)
        try:
            self._events_pub.bind(self.events_endpoint.replace("tcp://*", "tcp://0.0.0.0"))
        except zmq.ZMQError:
            self._events_pub.connect(self.events_endpoint)
        if self.ptt_command_endpoint:
            self._ptt_cmd = self._ctx.socket(zmq.PUSH)
            self._ptt_cmd.connect(self.ptt_command_endpoint)
        self._stop.clear()
        self._connected = True
        time.sleep(0.05)

    def stop(self) -> None:
        """Close sockets and stop background activity."""
        self._stop.set()
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=1.0)
            self._rx_thread = None
        for s in (self._rx_sub, self._tx_pub, self._ptt_cmd, self._events_pub):
            if s is not None:
                try:
                    s.close(linger=0)
                except zmq.ZMQError:
                    pass
        self._rx_sub = None
        self._tx_pub = None
        self._ptt_cmd = None
        self._events_pub = None
        self._connected = False

    def send_ptt_on(self) -> None:
        if self._ptt_cmd is None:
            raise RuntimeError("LinhtBridge.start() with ptt_command_endpoint set, or use LinHT PTT SUB")
        self._ptt_cmd.send(b"ptt_on")

    def send_ptt_off(self) -> None:
        if self._ptt_cmd is None:
            raise RuntimeError("LinhtBridge.start() with ptt_command_endpoint set, or use LinHT PTT SUB")
        self._ptt_cmd.send(b"ptt_off")

    def publish_rf_event(self, event: str) -> None:
        if self._events_pub is None:
            raise RuntimeError("LinhtBridge.start() first")
        self._events_pub.send(event.encode("utf-8"))

    def get_rx_socket(self):
        """Return SUB socket receiving RX IQ (advanced: GNU Radio ZMQ blocks usually bind/connect themselves)."""
        return self._rx_sub

    def get_tx_socket(self):
        """Return PUB socket for TX IQ (advanced)."""
        return self._tx_pub

    @property
    def is_connected(self) -> bool:
        return self._connected


class LinhtPttMsgSource(gr.basic_block):
    """
    GNU Radio 3.x message source: ZMQ SUB on ``endpoint`` yields PMT symbols on ``ptt``.
    Connect ``ptt`` to ``Keyed GDSS Spreader`` optional message port ``ptt``.
    """

    def __init__(self, endpoint: str = "ipc:///tmp/linht_ptt"):
        gr.basic_block.__init__(self, "LinhtPttMsgSource", [], [])
        self.message_port_register_out(pmt.intern("ptt"))
        if zmq is None:
            print("LinhtPttMsgSource: pyzmq not installed; PTT messages disabled")
            self._ctx = None
            return
        self._ctx = zmq.Context.instance()
        self._sock = self._ctx.socket(zmq.SUB)
        self._sock.setsockopt(zmq.SUBSCRIBE, b"")
        self._sock.setsockopt(zmq.RCVTIMEO, 50)
        self._sock.connect(endpoint)
        self._stop = threading.Event()
        self._thr = threading.Thread(target=self._loop, daemon=True)
        self._thr.start()

    def _loop(self) -> None:
        while not self._stop.is_set() and self._ctx is not None:
            try:
                raw = self._sock.recv(flags=zmq.NOBLOCK)
            except zmq.Again:
                time.sleep(0.01)
                continue
            except zmq.ZMQError:
                break
            try:
                s = raw.decode("utf-8", errors="ignore").strip()
            except Exception:
                continue
            if s == "ptt_on":
                self.message_port_pub(pmt.intern("ptt"), pmt.intern("ptt_on"))
            elif s == "ptt_off":
                self.message_port_pub(pmt.intern("ptt"), pmt.intern("ptt_off"))

    def stop(self) -> None:
        self._stop.set()
        if hasattr(self, "_thr") and self._thr.is_alive():
            self._thr.join(timeout=0.5)


class LinhtRfEventSink(gr.basic_block):
    """Publish short UTF-8 status strings to LinHT ``events`` SUB (flowgraph is publisher)."""

    def __init__(self, endpoint: str = "ipc:///tmp/linht_events"):
        gr.basic_block.__init__(self, "LinhtRfEventSink", [], [])
        self.message_port_register_in(pmt.intern("events"))
        self.set_msg_handler(pmt.intern("events"), self._handle)
        if zmq is None:
            self._sock = None
            return
        self._ctx = zmq.Context.instance()
        self._sock = self._ctx.socket(zmq.PUB)
        try:
            self._sock.bind(endpoint.replace("*", "0.0.0.0"))
        except zmq.ZMQError:
            self._sock.connect(endpoint)

    def _handle(self, msg) -> None:
        if self._sock is None:
            return
        if pmt.is_symbol(msg):
            s = pmt.symbol_to_string(msg)
        elif pmt.is_pair(msg) and pmt.is_blob(pmt.cdr(msg)):
            s = str(pmt.to_python(pmt.cdr(msg)), "utf-8", errors="ignore")
        else:
            return
        try:
            self._sock.send(s.encode("utf-8"))
        except zmq.ZMQError:
            pass
