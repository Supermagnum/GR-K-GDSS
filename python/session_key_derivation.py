#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Session key derivation and keyring wiring for gr-k-gdss.

Implements HKDF-based key derivation (RFC 5869) and optional Linux kernel
keyring storage for GDSS masking and related keys, as specified in the
covert stack implementation document. All session subkeys are 32 bytes
and are derived from a single ECDH shared secret (e.g. BrainpoolP256r1)
with domain-separation info strings.

Exported API:
  - derive_session_keys(ecdh_shared_secret, salt=None) -> dict of name -> 32-byte key
  - store_session_keys(keys) -> dict of name -> keyring ID
  - load_gdss_key(keyring_id) -> 32-byte GDSS masking key
  - gdss_nonce(session_id, tx_seq) -> 12-byte nonce for ChaCha20 masking
  - gdss_sync_burst_nonce(session_id) -> 12-byte nonce for sync-burst masking (keystream distinct from data)
  - payload_nonce(session_id, tx_seq) -> 96-bit nonce for payload AEAD
  - get_shared_secret_from_gnupg(my_private_pem, peer_public_pem) -> shared secret
  - keyring_available() -> bool
  - keyring_import_error() -> optional error message

Compatibility with gr-linux-crypto:
  KeyringHelper and CryptoHelpers are imported from gr_linux_crypto when available.
  For GDSS key storage/load, keyctl (keyutils) is required so 32-byte keys are
  stored as raw bytes; KeyringHelper.add_key stores a path, so load_gdss_key
  cannot return key bytes for keys stored that way. See docs/USAGE.md.
"""

from __future__ import annotations

import os
import subprocess
import shutil
from typing import Any, Dict, Optional, Type

from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


def _get_keyring_helper() -> Optional[Type[Any]]:
    """
    Lazy import of KeyringHelper from gr-linux-crypto.

    Tries multiple import paths so session_key_derivation loads even when
    gr_linux_crypto is missing. Returns the KeyringHelper class or None.
    """
    import importlib
    # If gr-linux-crypto source tree is set, add its python/ so keyring_helper can be imported
    gr_crypto_dir = os.environ.get("GR_LINUX_CRYPTO_DIR")
    if gr_crypto_dir:
        python_dir = os.path.join(gr_crypto_dir, "python")
        if os.path.isdir(python_dir) and python_dir not in __import__("sys").path:
            __import__("sys").path.insert(0, python_dir)
    # gr-linux-crypto: CMake installs to .../gr_linux_crypto/ (__init__.py, keyring_helper.py, crypto_helpers.py).
    # Standard install: from gr_linux_crypto import KeyringHelper
    for import_path in (
        "gr_linux_crypto",  # package root re-exports KeyringHelper, CryptoHelpers
        "gr_linux_crypto.keyring_helper",  # submodule (examples use this)
        "gr_linux_crypto.python.keyring_helper",  # if package has python subpackage
        "gnuradio.linux_crypto.python.keyring_helper",
        "gnuradio.linux_crypto.keyring_helper",
        "gnuradio.linux_crypto",
        "gnuradio.linux_crypto_python",
        "linux_crypto_python",
        "keyring_helper",  # when GR_LINUX_CRYPTO_DIR points to repo and python/ is on path
    ):
        try:
            mod = importlib.import_module(import_path)
            helper = getattr(mod, "KeyringHelper", None)
            if helper is None and import_path == "gnuradio.linux_crypto":
                sub = getattr(mod, "keyring_helper", None)
                if sub is not None:
                    helper = getattr(sub, "KeyringHelper", None)
            if helper is not None:
                return helper
        except ImportError:
            continue
        except AttributeError:
            continue
    return None


def _get_crypto_helpers() -> Optional[Any]:
    """
    Lazy import of CryptoHelpers from gr-linux-crypto.

    Used for ECDH (BrainpoolP256r1). Returns the CryptoHelpers class or None.
    Matches gr-linux-crypto python/__init__.py: from .crypto_helpers import CryptoHelpers.
    """
    try:
        from gr_linux_crypto import CryptoHelpers
        return CryptoHelpers
    except ImportError:
        try:
            from gr_linux_crypto.crypto_helpers import CryptoHelpers
            return CryptoHelpers
        except ImportError:
            try:
                from gr_linux_crypto.python.crypto_helpers import CryptoHelpers
                return CryptoHelpers
            except ImportError:
                try:
                    from crypto_helpers import CryptoHelpers  # type: ignore[no-redef]
                    return CryptoHelpers
                except ImportError:
                    return None


def _keyctl_path() -> Optional[str]:
    """Return path to keyctl binary if available, else None."""
    return shutil.which("keyctl")


def _keyctl_add_user_key(description: str, data: bytes, keyring: str = "@u") -> Optional[str]:
    """
    Add a user key via keyctl padd (pipe add), storing raw bytes as the key payload.
    Returns the key ID string, or None if keyctl is not available.
    """
    keyctl = _keyctl_path()
    if keyctl is None:
        return None

    result = subprocess.run(
        [keyctl, "padd", "user", description, keyring],
        input=data,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8", errors="replace").strip()


def _keyctl_read_key(key_id: int) -> Optional[bytes]:
    """
    Read key payload directly via keyctl read.
    Returns raw key bytes, or None if keyctl is not available or read fails (e.g. permission denied).
    """
    keyctl = _keyctl_path()
    if keyctl is None:
        return None
    try:
        result = subprocess.run(
            [keyctl, "read", str(key_id)],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        return None


def keyring_available() -> bool:
    """Return True if Linux keyring helper (gr-linux-crypto) is available."""
    return _get_keyring_helper() is not None


def keyring_import_error() -> Optional[str]:
    """Return the first import error message if keyring is not available, else None."""
    import importlib
    for import_path in (
        "gr_linux_crypto",
        "gr_linux_crypto.keyring_helper",
        "gr_linux_crypto.python.keyring_helper",
        "gnuradio.linux_crypto.python.keyring_helper",
        "gnuradio.linux_crypto.keyring_helper",
        "gnuradio.linux_crypto",
        "gnuradio.linux_crypto_python",
        "linux_crypto_python",
        "keyring_helper",
    ):
        try:
            mod = importlib.import_module(import_path)
            if getattr(mod, "KeyringHelper", None) is not None:
                return None
        except ImportError as e:
            return "{}: {}".format(import_path, e)
        except AttributeError:
            pass
    return "KeyringHelper not found in any tried path"


def derive_session_keys(
    ecdh_shared_secret: bytes,
    salt: Optional[bytes] = None,
) -> Dict[str, bytes]:
    """
    Derive all session subkeys from the ECDH shared secret using HKDF-SHA256.

    Uses domain-separation info strings so each key is cryptographically
    independent. Required for keyed GDSS: gdss_masking is used by the
    spreader/despreader; sync_pn and sync_timing are used for sync bursts.

    Args:
        ecdh_shared_secret: Raw shared secret from ECDH (e.g. 32 bytes from
            BrainpoolP256r1, 48 from P384r1, 64 from P512r1). At least 32 bytes
            recommended; longer secrets are used in full by HKDF.
        salt: Optional 32-byte salt for HKDF. Defaults to 32 zero bytes.

    Returns:
        Dict with keys: "payload_enc", "gdss_masking", "sync_pn", "sync_timing".
        Each value is 32 bytes.

    Raises:
        Nothing; HKDF may raise if inputs are invalid.
    """
    if salt is None:
        salt = bytes(32)

    def hkdf_expand(info: bytes) -> bytes:
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=info,
        ).derive(ecdh_shared_secret)

    return {
        "payload_enc": hkdf_expand(b"payload-chacha20poly1305-v1"),
        "gdss_masking": hkdf_expand(b"gdss-chacha20-masking-v1"),
        "sync_pn": hkdf_expand(b"sync-dsss-pn-sequence-v1"),
        "sync_timing": hkdf_expand(b"sync-burst-timing-offset-v1"),
    }


def store_session_keys(keys: Dict[str, bytes]) -> Dict[str, str]:
    """
    Store derived session keys in the Linux kernel keyring.

    When keyctl is available, uses keyctl padd so key payloads are raw bytes;
    load_gdss_key then returns key bytes. When only gr-linux-crypto
    KeyringHelper is available, uses add_key (keyring may store a path);
    in that case load_gdss_key might not return raw key bytes. Prefer
    having keyctl available for GDSS key storage and load.

    Args:
        keys: Dict mapping key name to 32-byte key bytes (e.g. output of
            derive_session_keys).

    Returns:
        Dict mapping key name to keyring key ID (string). Use the ID for
        gdss_masking with load_gdss_key(int(id)) when keyctl was used.

    Raises:
        RuntimeError: If neither keyctl nor KeyringHelper is available.
    """
    use_keyctl = _keyctl_path() is not None

    KeyringHelper = _get_keyring_helper()
    if KeyringHelper is None and not use_keyctl:
        raise RuntimeError(
            "Linux keyring helper not available (gr-linux-crypto not installed). "
            "Install gr-linux-crypto and ensure keyctl (keyutils) is on PATH for GDSS key storage."
        )

    helper = None
    if KeyringHelper is not None and not use_keyctl:
        try:
            helper = KeyringHelper()
        except RuntimeError as e:
            if "keyctl" in str(e).lower():
                raise RuntimeError(
                    "KeyringHelper requires keyctl (keyutils). Install keyutils for keyring support. "
                    "For GDSS, keyctl is required so 32-byte keys are stored as raw bytes (keyctl padd)."
                ) from e
            raise

    ids: Dict[str, str] = {}
    for name, key_bytes in keys.items():
        if use_keyctl:
            key_id = _keyctl_add_user_key(f"sdr_session_{name}", key_bytes)
            if key_id is None:
                raise RuntimeError("keyctl is not available to store session keys")
            ids[name] = key_id
        else:
            assert helper is not None
            ids[name] = helper.add_key("user", f"sdr_session_{name}", key_bytes)
    return ids


def _parse_keyctl_read_output(raw: bytes) -> bytes:
    """
    If KeyringHelper.read_key returns keyctl's text description (e.g. '16 bytes of data in key:\\n' + hex),
    parse the hex and return the key bytes. Otherwise return raw unchanged.
    """
    try:
        text = raw.decode("utf-8", errors="replace")
        if "bytes of data in key" not in text:
            return raw
        lines = text.split("\n")[1:]
        hex_chars = "0123456789abcdefABCDEF"
        hex_part = "".join(c for line in lines for c in line if c in hex_chars)
        if not hex_part or len(hex_part) % 2 != 0:
            return raw
        return bytes.fromhex(hex_part)
    except (ValueError, UnicodeDecodeError):
        return raw


def load_gdss_key(keyring_id: int) -> bytes:
    """
    Load the 32-byte GDSS masking key from the kernel keyring by key ID.

    Prefers direct keyctl read (returns raw bytes). Falls back to
    gr-linux-crypto KeyringHelper when keyctl is unavailable. For keys
    stored with keyctl padd, the payload is raw bytes. For keys stored
    with KeyringHelper.add_key, the payload may be a path string; prefer
    storing GDSS keys via store_session_keys when keyctl is available.

    Args:
        keyring_id: Kernel keyring key ID (integer), as returned by
            store_session_keys for "gdss_masking".

    Returns:
        32-byte GDSS masking key for use with kgdss_spreader_cc / kgdss_despreader_cc.

    Raises:
        RuntimeError: If keyring helper is not available or read fails.
    """
    raw = _keyctl_read_key(int(keyring_id))
    if raw is not None:
        out = _parse_keyctl_read_output(raw)
        if len(out) != 32:
            raise ValueError(
                "load_gdss_key: keyring key is not 32 bytes (got {}). "
                "GDSS requires a 32-byte key. Ensure the key was stored with keyctl padd or "
                "store_session_keys with keyctl available.".format(len(out))
            )
        return out

    KeyringHelper = _get_keyring_helper()
    if KeyringHelper is None:
        raise RuntimeError("Linux keyring helper not available (gr-linux-crypto not installed)")
    try:
        helper = KeyringHelper()
    except RuntimeError as e:
        if "keyctl" in str(e).lower():
            raise RuntimeError(
                "KeyringHelper requires keyctl (keyutils). Install keyutils and ensure keyctl is on PATH. "
                "For GDSS key storage/load, keyctl is required to read/write raw 32-byte keys."
            ) from e
        raise
    raw_helper = helper.read_key(str(int(keyring_id)))
    out = _parse_keyctl_read_output(raw_helper)
    if len(out) != 32:
        raise ValueError(
            "load_gdss_key: keyring did not return 32 bytes (got {}). "
            "gr-linux-crypto KeyringHelper.add_key stores a path, not raw key bytes. "
            "Use keyctl for GDSS: install keyutils and use store_session_keys when keyctl is available."
            .format(len(out))
        )
    return out


def get_shared_secret_from_gnupg(
    my_private_key_pem: bytes,
    peer_public_key_pem: bytes,
) -> bytes:
    """
    Perform ECDH using pre-existing BrainpoolP256r1 keys to produce a shared secret.

    Keys are typically exported from GnuPG and passed as PEM-encoded bytes.
    The shared secret is used as input to derive_session_keys().

    Args:
        my_private_key_pem: PEM-encoded BrainpoolP256r1 private key.
        peer_public_key_pem: PEM-encoded BrainpoolP256r1 public key.

    Returns:
        Raw ECDH shared secret (e.g. 32 bytes). Pass to derive_session_keys().

    Raises:
        RuntimeError: If CryptoHelpers (gr-linux-crypto) is not installed.
    """
    CryptoHelpers = _get_crypto_helpers()
    if CryptoHelpers is None:
        raise RuntimeError("CryptoHelpers not available (gr-linux-crypto not installed)")
    crypto = CryptoHelpers()
    private_key = crypto.load_brainpool_private_key(my_private_key_pem)
    public_key = crypto.load_brainpool_public_key(peer_public_key_pem)
    return crypto.brainpool_ecdh(private_key, public_key)


def gdss_nonce(session_id: int, tx_seq: int) -> bytes:
    """
    Build the 12-byte nonce for the GDSS ChaCha20 masking keystream.

    Matches the nonce format expected by the C++ spreader/despreader
    (libsodium ChaCha20 IETF: 4-byte session ID + 8-byte TX sequence).

    Args:
        session_id: Session identifier (e.g. 1, 2). Encoded big-endian, 4 bytes.
        tx_seq: Transmission sequence number. Encoded big-endian, 8 bytes.

    Returns:
        12-byte nonce for ChaCha20 IETF (no counter in nonce; counter starts at 0).
    """
    return session_id.to_bytes(4, "big") + tx_seq.to_bytes(8, "big")


# Reserved tx_seq value so sync-burst mask keystream does not overlap with data.
SYNC_BURST_TX_SEQ = (1 << 64) - 1


def gdss_sync_burst_nonce(session_id: int) -> bytes:
    """
    Return the 12-byte nonce for sync-burst keyed Gaussian masking.

    Use this (with gdss_masking key) when calling apply_keyed_gaussian_mask
    so the sync burst keystream is distinct from the data keystream. Same
    session_id as the link; tx_seq is reserved (SYNC_BURST_TX_SEQ).

    Args:
        session_id: Session identifier.

    Returns:
        12-byte nonce for ChaCha20 IETF.
    """
    return gdss_nonce(session_id, SYNC_BURST_TX_SEQ)


def payload_nonce(session_id: int, tx_seq: int) -> bytes:
    """
    Build the 96-bit nonce for payload ChaCha20-Poly1305 AEAD.

    Format: 3-byte prefix "pay" + session_id (4 bytes big-endian) + tx_seq (5 bytes big-endian).

    Args:
        session_id: Session identifier.
        tx_seq: Transmission sequence number (truncated to 5 bytes).

    Returns:
        12-byte nonce for payload encryption.
    """
    return b"pay" + session_id.to_bytes(4, "big") + tx_seq.to_bytes(5, "big")
