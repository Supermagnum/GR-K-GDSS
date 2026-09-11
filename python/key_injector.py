"""
Key injector block for gr-k-gdss: provides ChaCha20 key and nonce from session
key derivation and sends them to keyed GDSS spreader/despreader set_key ports.

Key and nonce are always taken from session key derivation (no manual entry).
Either pass shared_secret or keyring_id at construction, or feed shared_secret
via the shared_secret message port. The block sends the set_key message
automatically when the flowgraph starts (no trigger connection required).

Connect key_out to the set_key message input of kgdss_spreader_cc and
kgdss_despreader_cc.
"""

from __future__ import annotations

from typing import Any, Optional

from gnuradio import gr
from gnuradio.gr import pmt

try:
    from .session_key_derivation import (
        allocate_gdss_nonce_counters,
        derive_session_keys,
        derive_session_keys_from_galdralag,
        galdralag_kdf_available,
        gdss_nonce,
        load_gdss_key,
        reserve_gdss_nonce_counters,
    )
except ImportError:
    allocate_gdss_nonce_counters = None
    derive_session_keys = None
    derive_session_keys_from_galdralag = None
    galdralag_kdf_available = None
    gdss_nonce = None
    load_gdss_key = None
    reserve_gdss_nonce_counters = None


def _normalize_key_derivation(mode: str) -> str:
    """Match gr-linux-crypto gdss_set_key_source_block naming."""
    m = (mode or "gr_k_gdss").strip().lower().replace("-", "_")
    if m in ("gr_k_gdss", "grkgdss", "gr_k_gdss_default", "default"):
        return "gr_k_gdss"
    if m in ("galdralag", "galdr"):
        return "galdralag"
    raise ValueError(
        "key_derivation must be 'gr_k_gdss' (default) or 'galdralag' "
        "(requires epk_initiator and epk_responder when using shared_secret)"
    )


def _build_set_key_msg(gdss_key: bytes, nonce: bytes) -> Any:
    if len(gdss_key) != 32 or len(nonce) != 12:
        raise ValueError("gdss_masking must be 32 bytes, nonce 12 bytes")
    return pmt.dict_add(
        pmt.dict_add(
            pmt.make_dict(),
            pmt.intern("key"),
            pmt.init_u8vector(32, list(gdss_key)),
        ),
        pmt.intern("nonce"),
        pmt.init_u8vector(12, list(nonce)),
    )


_STATIC_NONCE_HELP = (
    "tx_seq=0 is a historically unsafe default that invites (key, nonce) reuse "
    "across sessions when gdss_masking is derived from static long-term ECDH. "
    "Omit tx_seq to allocate a persisted counter via allocate_gdss_nonce_counters, "
    "pass a non-zero tx_seq, or set allow_static_nonce=True only if you accept the risk "
    "and coordinate the same pair on the peer."
)


class key_injector(gr.basic_block):
    """
    GNU Radio block that provides GDSS key and nonce from session key derivation
    and publishes them as a set_key PMT message. No manual key/nonce entry.

    Key and nonce come from: (1) keyring_id (load key from keyring), or
    (2) shared_secret at construction (derive via HKDF), or (3) shared_secret
    message input (derive when message arrives). Session_id and tx_seq set the
    nonce. The block sends the key message automatically in start() so no
    trigger connection is needed. Connect key_out to set_key of spreader and
    despreader.

    **Nonce allocation:** If ``tx_seq`` is omitted (``None``), the injector
    allocates the next ``(session_id, tx_seq)`` via
    ``allocate_gdss_nonce_counters`` (persisted per masking-key fingerprint).
    Explicit ``tx_seq=0`` requires ``allow_static_nonce=True``.

    **Galdralag / gr-linux-crypto:** When ``key_derivation="galdralag"`` and
    ``shared_secret`` is set at construction, pass ``epk_initiator`` and
    ``epk_responder`` (uncompressed SEC1 ephemeral public keys). This matches
    **gr-linux-crypto** ``gdss_set_key_source_block`` with
    ``key_derivation="galdralag"``. The ``shared_secret`` message port path
    always uses the default gr-k-gdss HKDF profile (no epk on the wire).
    """

    def __init__(
        self,
        shared_secret: Optional[bytes] = None,
        session_id: Optional[int] = None,
        tx_seq: Optional[int] = None,
        keyring_id: Optional[int] = None,
        key_derivation: str = "gr_k_gdss",
        epk_initiator: Optional[bytes] = None,
        epk_responder: Optional[bytes] = None,
        allow_static_nonce: bool = False,
        nonce_state_path: Optional[str] = None,
    ) -> None:
        if derive_session_keys is None or gdss_nonce is None:
            raise RuntimeError(
                "key_injector requires session_key_derivation (derive_session_keys, gdss_nonce)"
            )
        if allocate_gdss_nonce_counters is None or reserve_gdss_nonce_counters is None:
            raise RuntimeError(
                "key_injector requires session_key_derivation nonce counter helpers"
            )
        mode = _normalize_key_derivation(key_derivation)
        if keyring_id is not None and shared_secret is not None:
            raise ValueError("provide exactly one of shared_secret or keyring_id")
        if keyring_id is None and (shared_secret is None or len(shared_secret) < 32):
            if shared_secret is not None:
                raise ValueError("shared_secret must be at least 32 bytes")
            # deferred: wait for shared_secret message on shared_secret port
        if mode == "galdralag":
            if keyring_id is not None:
                pass  # raw gdss bytes from keyring; derivation mode ignored
            elif shared_secret is not None and len(shared_secret) >= 32:
                if epk_initiator is None or epk_responder is None:
                    raise ValueError(
                        "key_derivation='galdralag' requires epk_initiator and epk_responder "
                        "when using shared_secret at construction"
                    )
                if (
                    derive_session_keys_from_galdralag is None
                    or galdralag_kdf_available is None
                    or not galdralag_kdf_available()
                ):
                    raise RuntimeError(
                        "key_derivation='galdralag' requires gr-linux-crypto with "
                        "derive_galdralag_session_keys (install gr-linux-crypto or set GR_LINUX_CRYPTO_DIR)"
                    )
            else:
                raise ValueError(
                    "key_derivation='galdralag' requires shared_secret at construction "
                    "(with epk_initiator and epk_responder); the shared_secret message port "
                    "only supports the default gr_k_gdss profile"
                )

        gr.basic_block.__init__(
            self,
            name="key_injector",
            in_sig=None,
            out_sig=None,
        )
        self.message_port_register_out(pmt.intern("key_out"))
        self.message_port_register_in(pmt.intern("trigger"))
        self.set_msg_handler(pmt.intern("trigger"), self._on_trigger)

        self._preferred_session_id = 1 if session_id is None else int(session_id)
        self._tx_seq_arg = tx_seq
        self._allow_static_nonce = bool(allow_static_nonce)
        self._nonce_state_path = nonce_state_path
        self._session_id = self._preferred_session_id
        self._tx_seq = 0
        self._msg: Any = None

        if keyring_id is not None:
            if load_gdss_key is None:
                raise RuntimeError("keyring_id requires session_key_derivation.load_gdss_key")
            gdss_key = load_gdss_key(int(keyring_id))
            self._session_id, self._tx_seq, nonce = self._resolve_nonce(gdss_key)
            self._msg = _build_set_key_msg(gdss_key, nonce)
        elif shared_secret is not None and len(shared_secret) >= 32:
            if mode == "galdralag":
                assert epk_initiator is not None and epk_responder is not None
                keys = derive_session_keys_from_galdralag(
                    shared_secret, epk_initiator, epk_responder
                )
            else:
                keys = derive_session_keys(shared_secret)
            gdss_key = keys["gdss_masking"]
            self._session_id, self._tx_seq, nonce = self._resolve_nonce(gdss_key)
            self._msg = _build_set_key_msg(gdss_key, nonce)
        else:
            self.message_port_register_in(pmt.intern("shared_secret"))
            self.set_msg_handler(pmt.intern("shared_secret"), self._on_shared_secret)

    def _resolve_nonce(self, gdss_key: bytes) -> tuple[int, int, bytes]:
        """Return (session_id, tx_seq, nonce_bytes) with reuse protections."""
        if self._tx_seq_arg is None:
            sid, tx = allocate_gdss_nonce_counters(
                gdss_key,
                state_path=self._nonce_state_path,
                preferred_session_id=self._preferred_session_id,
            )
            return sid, tx, gdss_nonce(sid, tx)

        sid = self._preferred_session_id
        tx = int(self._tx_seq_arg)
        if tx == 0 and not self._allow_static_nonce:
            raise ValueError(_STATIC_NONCE_HELP)
        if not self._allow_static_nonce:
            reserve_gdss_nonce_counters(
                gdss_key, sid, tx, state_path=self._nonce_state_path
            )
        return sid, tx, gdss_nonce(sid, tx)

    def _on_shared_secret(self, msg: Any) -> None:
        """On shared_secret message: derive key+nonce and publish set_key."""
        if not pmt.is_u8vector(msg):
            return
        data = bytes(pmt.u8vector_elements(msg))
        if len(data) < 32:
            return
        # Use full secret (supports 32/40/48/64-byte Brainpool shared secrets)
        secret = data
        keys = derive_session_keys(secret)
        gdss_key = keys["gdss_masking"]
        self._session_id, self._tx_seq, nonce = self._resolve_nonce(gdss_key)
        self._msg = _build_set_key_msg(gdss_key, nonce)
        self.message_port_pub(pmt.intern("key_out"), self._msg)

    def _on_trigger(self, msg: Any) -> None:
        """On trigger: republish current key message if built."""
        if self._msg is not None:
            self.message_port_pub(pmt.intern("key_out"), self._msg)

    def start(self) -> bool:
        """Send key message once when flowgraph starts (no manual trigger)."""
        result = super().start()
        if result and self._msg is not None:
            self.message_port_pub(pmt.intern("key_out"), self._msg)
        return result

    def inject(self) -> None:
        """
        Send the key message once. Called automatically in start(); use to
        re-send key after flowgraph is running if needed.
        """
        if self._msg is not None:
            self.message_port_pub(pmt.intern("key_out"), self._msg)
