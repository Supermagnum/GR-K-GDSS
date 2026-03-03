"""
Key injector block: formats GDSS key and nonce as a PMT message and sends
to keyed GDSS spreader/despreader set_key ports.

Use with message passing: connect a message source (e.g. message strobe at
flowgraph start) to the trigger port, or call inject() once after flowgraph
start to send the key to all connected set_key ports.
"""

from gnuradio import gr
from gnuradio.gr import pmt

try:
    from .session_key_derivation import derive_session_keys, gdss_nonce
except ImportError:
    derive_session_keys = None
    gdss_nonce = None


class key_injector(gr.basic_block):
    """
    Derives GDSS key and nonce from shared_secret (e.g. ECDH) and session_id/tx_seq,
    formats them as a PMT dict with "key" (32 bytes) and "nonce" (12 bytes),
    and publishes to the key_out message port. Connect key_out to the set_key
    message input of kgdss_spreader_cc and kgdss_despreader_cc.

    shared_secret: at least 32 bytes. Can come from gr-linux-crypto
    CryptoHelpers.brainpool_ecdh(private_key, peer_public_key), or from
    kgdss.get_shared_secret_from_gnupg(my_private_key_pem, peer_public_key_pem).

    When the trigger port receives any message, the block publishes the key
    message. Alternatively call inject() once at flowgraph start to send
    the key without a trigger connection.
    """

    def __init__(self, shared_secret: bytes, session_id: int, tx_seq: int):
        if derive_session_keys is None or gdss_nonce is None:
            raise RuntimeError("key_injector requires session_key_derivation (derive_session_keys, gdss_nonce)")
        if len(shared_secret) < 32:
            raise ValueError("shared_secret must be at least 32 bytes")
        gr.basic_block.__init__(
            self,
            name="key_injector",
            in_sig=None,
            out_sig=None,
        )
        self.message_port_register_out(pmt.intern("key_out"))
        self.message_port_register_in(pmt.intern("trigger"))
        self.set_msg_handler(pmt.intern("trigger"), self._on_trigger)

        keys = derive_session_keys(shared_secret)
        gdss_key = keys["gdss_masking"]
        nonce = gdss_nonce(session_id, tx_seq)
        if len(gdss_key) != 32 or len(nonce) != 12:
            raise ValueError("gdss_masking must be 32 bytes, gdss_nonce 12 bytes")
        self._msg = pmt.dict_add(
            pmt.dict_add(
                pmt.make_dict(),
                pmt.intern("key"),
                pmt.init_u8vector(32, list(gdss_key)),
            ),
            pmt.intern("nonce"),
            pmt.init_u8vector(12, list(nonce)),
        )

    def _on_trigger(self, msg):
        self.message_port_pub(pmt.intern("key_out"), self._msg)

    def inject(self):
        """Send the key message once. Call at flowgraph start to key the blocks."""
        self.message_port_pub(pmt.intern("key_out"), self._msg)
