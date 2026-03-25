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
        gdss_sync_burst_nonce,
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
    gdss_sync_burst_nonce = None
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
        derive_sync_amplitude_scaling,
        gaussian_envelope,
        apply_keyed_gaussian_mask,
    )
except ImportError:
    derive_sync_schedule = None
    derive_sync_pn_sequence = None
    derive_sync_amplitude_scaling = None
    gaussian_envelope = None
    apply_keyed_gaussian_mask = None

try:
    from .p372_baseline import load_p372_params, P372Params
    from .p372_receiver_profile import (
        P372ReceiverProfile,
        p372_expected_psd_profile_dbm_per_hz,
        calibrate_p372_profile_to_measured_psd,
    )
except ImportError:
    load_p372_params = None
    P372Params = None
    P372ReceiverProfile = None
    p372_expected_psd_profile_dbm_per_hz = None
    calibrate_p372_profile_to_measured_psd = None

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
    "gdss_sync_burst_nonce",
    "payload_nonce",
    "keyring_available",
    "keyring_import_error",
    "derive_sync_schedule",
    "derive_sync_pn_sequence",
    "derive_sync_amplitude_scaling",
    "gaussian_envelope",
    "apply_keyed_gaussian_mask",
    "load_p372_params",
    "P372Params",
    "P372ReceiverProfile",
    "p372_expected_psd_profile_dbm_per_hz",
    "calibrate_p372_profile_to_measured_psd",
    "kgdss_spreader_cc",
    "kgdss_despreader_cc",
    "kgdss_sync_state",
]

