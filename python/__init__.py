"""
gr-k-gdss - Keyed Gaussian-Distributed Spread-Spectrum
"""

try:
    from .session_key_derivation import (
        derive_session_keys,
        store_session_keys,
        load_gdss_key,
        get_shared_secret_from_gnupg,
        gdss_nonce,
        payload_nonce,
        keyring_available,
        keyring_import_error,
    )
except ImportError:
    derive_session_keys = None
    store_session_keys = None
    load_gdss_key = None
    get_shared_secret_from_gnupg = None
    gdss_nonce = None
    payload_nonce = None
    keyring_available = None
    keyring_import_error = None

try:
    from .key_injector import key_injector
except ImportError:
    key_injector = None

try:
    from .sync_burst_utils import (
        derive_sync_schedule,
        derive_sync_pn_sequence,
        gaussian_envelope,
    )
except ImportError:
    derive_sync_schedule = None
    derive_sync_pn_sequence = None
    gaussian_envelope = None

try:
    from .kgdss_python import (
        kgdss_spreader_cc,
        kgdss_despreader_cc,
        kgdss_sync_state,
    )
except ImportError:
    kgdss_spreader_cc = None
    kgdss_despreader_cc = None
    kgdss_sync_state = None

__all__ = [
    "key_injector",
    "derive_session_keys",
    "store_session_keys",
    "load_gdss_key",
    "get_shared_secret_from_gnupg",
    "gdss_nonce",
    "payload_nonce",
    "keyring_available",
    "keyring_import_error",
    "derive_sync_schedule",
    "derive_sync_pn_sequence",
    "gaussian_envelope",
    "kgdss_spreader_cc",
    "kgdss_despreader_cc",
    "kgdss_sync_state",
]

