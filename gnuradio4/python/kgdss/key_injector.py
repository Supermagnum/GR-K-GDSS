"""
Key injector for gr-k-gdss (GNU Radio 4 port).

Produces the set_key message for KgdssSpreaderCc and KgdssDespreaderCc.
The message body must be a property_map with two entries:
    "key"   -> Tensor<uint8_t> of exactly 32 bytes (ChaCha20 key)
    "nonce" -> Tensor<uint8_t> of exactly 12 bytes (IETF nonce)

GR4 Python bindings are not yet available.  Two integration paths are
provided, in order of preference for current use:

1.  GR3-runtime path (gr.basic_block + pmt):
    Instantiate KeyInjectorBlock and connect its key_out port to the
    set_key port of the C++ block.  The PMT u8vector encoding is
    compatible when routed via a GR3/GR4 bridge that converts PMT
    u8vectors to gr::Tensor<uint8_t> before delivery.

2.  Standalone bytes path (no GNU Radio import required):
    Call build_set_key_dict(key, nonce) to obtain a plain Python dict
    {"key": bytes, "nonce": bytes}.  Serialize with to_bytes_payload()
    for reading by a companion C++ block.

Key derivation is done via session_key_derivation.derive_session_keys
(HKDF, info b"gdss-chacha20-masking-v1") as in gr-linux-crypto GR4.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from .session_key_derivation import (
        derive_session_keys,
        derive_session_keys_from_galdralag,
        galdralag_kdf_available,
        gdss_nonce,
        load_gdss_key,
    )
except ImportError:
    derive_session_keys = None
    derive_session_keys_from_galdralag = None
    galdralag_kdf_available = None
    gdss_nonce = None
    load_gdss_key = None


def _normalize_key_derivation(mode: str) -> str:
    m = (mode or "gr_k_gdss").strip().lower().replace("-", "_")
    if m in ("gr_k_gdss", "grkgdss", "gr_k_gdss_default", "default"):
        return "gr_k_gdss"
    if m in ("galdralag", "galdr"):
        return "galdralag"
    raise ValueError(
        "key_derivation must be 'gr_k_gdss' (default) or 'galdralag'"
    )


def build_set_key_dict(key: bytes, nonce: bytes) -> Dict[str, bytes]:
    """
    Return a plain Python dict {"key": bytes(32), "nonce": bytes(12)}.

    When GR4 Python bindings become available, wrap each value as a
    gr::Tensor<uint8_t> and pass the resulting property_map as the body of
    a gr::Message sent to the block's set_key port.  The C++ block's
    copyKeyNonceFromDict expects Tensor<uint8_t> entries keyed "key" and
    "nonce".
    """
    if len(key) != 32:
        raise ValueError("key must be exactly 32 bytes")
    if len(nonce) != 12:
        raise ValueError("nonce must be exactly 12 bytes")
    return {"key": bytes(key), "nonce": bytes(nonce)}


def to_bytes_payload(key: bytes, nonce: bytes) -> bytes:
    """
    Serialize key+nonce as 44 raw bytes (32 key || 12 nonce) for out-of-band
    injection via a C++ FileKeyLoader block or similar mechanism.
    """
    if len(key) != 32 or len(nonce) != 12:
        raise ValueError("key must be 32 bytes and nonce must be 12 bytes")
    return bytes(key) + bytes(nonce)


def _build_pmt_msg(key: bytes, nonce: bytes) -> Any:
    """Build a GR3 PMT dict message compatible with pmt.dict_add / pmt.intern."""
    from gnuradio.gr import pmt  # type: ignore[import]
    return pmt.dict_add(
        pmt.dict_add(
            pmt.make_dict(),
            pmt.intern("key"),
            pmt.init_u8vector(32, list(key)),
        ),
        pmt.intern("nonce"),
        pmt.init_u8vector(12, list(nonce)),
    )


class KeyInjector:
    """
    Key injector compatible with the gr-linux-crypto gnuradio4 pattern.

    Derives key and nonce via session_key_derivation and builds the
    set_key PMT message.  When GNU Radio 3 runtime is available,
    instantiate as a gr.basic_block (see KeyInjectorBlock below).

    For standalone use (no GNU Radio import):
        ki = KeyInjector(shared_secret=..., session_id=1, tx_seq=0)
        msg = ki.build_gr3_pmt_msg()   # GR3 PMT pmt.dict
        raw = ki.to_bytes()            # 44 raw bytes
        d   = ki.to_dict()             # plain {"key": bytes, "nonce": bytes}
    """

    def __init__(
        self,
        shared_secret: Optional[bytes] = None,
        session_id: int = 1,
        tx_seq: int = 0,
        keyring_id: Optional[int] = None,
        key_derivation: str = "gr_k_gdss",
        epk_initiator: Optional[bytes] = None,
        epk_responder: Optional[bytes] = None,
    ) -> None:
        if derive_session_keys is None or gdss_nonce is None:
            raise RuntimeError(
                "KeyInjector requires session_key_derivation "
                "(derive_session_keys, gdss_nonce)"
            )
        mode = _normalize_key_derivation(key_derivation)

        self._key: Optional[bytes] = None
        self._nonce: Optional[bytes] = None

        if keyring_id is not None and shared_secret is not None:
            raise ValueError("provide exactly one of shared_secret or keyring_id")

        if keyring_id is not None:
            if load_gdss_key is None:
                raise RuntimeError("keyring_id requires session_key_derivation.load_gdss_key")
            gdss_key = load_gdss_key(int(keyring_id))
            nonce = gdss_nonce(session_id, tx_seq)
        elif shared_secret is not None and len(shared_secret) >= 32:
            if mode == "galdralag":
                if (
                    derive_session_keys_from_galdralag is None
                    or galdralag_kdf_available is None
                    or not galdralag_kdf_available()
                ):
                    raise RuntimeError(
                        "key_derivation='galdralag' requires gr-linux-crypto"
                    )
                if epk_initiator is None or epk_responder is None:
                    raise ValueError(
                        "key_derivation='galdralag' requires epk_initiator and epk_responder"
                    )
                keys = derive_session_keys_from_galdralag(
                    shared_secret, epk_initiator, epk_responder
                )
            else:
                keys = derive_session_keys(shared_secret)
            gdss_key = keys["gdss_masking"]
            nonce = gdss_nonce(session_id, tx_seq)
        else:
            return

        self._key = bytes(gdss_key)
        self._nonce = bytes(nonce)

    @property
    def ready(self) -> bool:
        return self._key is not None and self._nonce is not None

    def to_dict(self) -> Dict[str, bytes]:
        if not self.ready:
            raise RuntimeError("key material not derived yet")
        return build_set_key_dict(self._key, self._nonce)  # type: ignore[arg-type]

    def to_bytes(self) -> bytes:
        if not self.ready:
            raise RuntimeError("key material not derived yet")
        return to_bytes_payload(self._key, self._nonce)  # type: ignore[arg-type]

    def build_gr3_pmt_msg(self) -> Any:
        """
        Build a GR3 PMT dict message (requires gnuradio.gr.pmt to be importable).
        This matches the gr-linux-crypto gnuradio4 gdss_set_key_source pattern.
        Connect the result to a set_key message port of spreader or despreader.
        """
        if not self.ready:
            raise RuntimeError("key material not derived yet")
        return _build_pmt_msg(self._key, self._nonce)  # type: ignore[arg-type]


try:
    from gnuradio import gr  # type: ignore[import]
    from gnuradio.gr import pmt  # type: ignore[import]

    class KeyInjectorBlock(gr.basic_block):
        """
        GNU Radio 3-runtime block that emits set_key PMT messages.

        Matches the gr-linux-crypto gnuradio4 gdss_set_key_source pattern.
        Connect key_out to the set_key port of KgdssSpreaderCc /
        KgdssDespreaderCc.  The message is sent automatically in start();
        connect a trigger message to re-send if needed.
        """

        def __init__(
            self,
            shared_secret: Optional[bytes] = None,
            session_id: int = 1,
            tx_seq: int = 0,
            keyring_id: Optional[int] = None,
            key_derivation: str = "gr_k_gdss",
            epk_initiator: Optional[bytes] = None,
            epk_responder: Optional[bytes] = None,
        ) -> None:
            gr.basic_block.__init__(
                self,
                name="key_injector",
                in_sig=None,
                out_sig=None,
            )
            self.message_port_register_out(pmt.intern("key_out"))
            self.message_port_register_in(pmt.intern("trigger"))
            self.set_msg_handler(pmt.intern("trigger"), self._on_trigger)

            self._ki = KeyInjector(
                shared_secret=shared_secret,
                session_id=session_id,
                tx_seq=tx_seq,
                keyring_id=keyring_id,
                key_derivation=key_derivation,
                epk_initiator=epk_initiator,
                epk_responder=epk_responder,
            )
            self._msg: Any = self._ki.build_gr3_pmt_msg() if self._ki.ready else None

        def _on_trigger(self, _msg: Any) -> None:
            if self._msg is not None:
                self.message_port_pub(pmt.intern("key_out"), self._msg)

        def start(self) -> bool:
            result = super().start()
            if result and self._msg is not None:
                self.message_port_pub(pmt.intern("key_out"), self._msg)
            return result

        def inject(self) -> None:
            """Re-send the key message; useful after flowgraph is running."""
            if self._msg is not None:
                self.message_port_pub(pmt.intern("key_out"), self._msg)

    key_injector = KeyInjectorBlock

except ImportError:
    key_injector = None  # type: ignore[assignment,misc]
