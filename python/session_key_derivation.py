#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Session key derivation and keyring wiring for gr-k-gdss.

Implements HKDF-based key derivation and Linux kernel keyring storage
for GDSS masking and related keys, as specified in the covert stack
implementation document.
"""

import os
import subprocess
import shutil
from typing import Dict, Optional

from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


def _get_keyring_helper():
    """Lazy import so session_key_derivation loads even when gr_linux_crypto is missing."""
    import importlib
    # If gr-linux-crypto source tree is set, add its python/ so keyring_helper can be imported
    gr_crypto_dir = os.environ.get("GR_LINUX_CRYPTO_DIR")
    if gr_crypto_dir:
        python_dir = os.path.join(gr_crypto_dir, "python")
        if os.path.isdir(python_dir) and python_dir not in __import__("sys").path:
            __import__("sys").path.insert(0, python_dir)
    # gr-linux-crypto installs as gr_linux_crypto; __init__.py re-exports KeyringHelper.
    # Standard install: from gr_linux_crypto import KeyringHelper
    for import_path in (
        "gr_linux_crypto",  # installed package re-exports KeyringHelper, CryptoHelpers
        "gr_linux_crypto.keyring_helper",
        "gr_linux_crypto.python.keyring_helper",
        "gnuradio.linux_crypto.python.keyring_helper",
        "gnuradio.linux_crypto.keyring_helper",
        "gnuradio.linux_crypto",
        "gnuradio.linux_crypto_python",
        "linux_crypto_python",
        "keyring_helper",  # when GR_LINUX_CRYPTO_DIR/python is on path (source tree)
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


def _get_crypto_helpers():
    """Lazy import so session_key_derivation loads even when gr_linux_crypto is missing."""
    try:
        from gr_linux_crypto import CryptoHelpers
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


def derive_session_keys(ecdh_shared_secret: bytes, salt: Optional[bytes] = None) -> Dict[str, bytes]:
    """
    Derives all session subkeys from ECDH shared secret via HKDF.
    Returns dict with named keys, each 32 bytes.
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
    """Store derived keys in kernel keyring. Returns keyring IDs."""
    use_keyctl = _keyctl_path() is not None

    KeyringHelper = _get_keyring_helper()
    if KeyringHelper is None and not use_keyctl:
        raise RuntimeError("Linux keyring helper not available (gr-linux-crypto not installed)")

    helper = KeyringHelper() if KeyringHelper is not None else None
    ids: Dict[str, str] = {}
    for name, key_bytes in keys.items():
        if use_keyctl:
            key_id = _keyctl_add_user_key(f"sdr_session_{name}", key_bytes)
            if key_id is None:
                raise RuntimeError("keyctl is not available to store session keys")
            ids[name] = key_id
        else:
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
    # Prefer direct keyctl read; keyctl may still output text format when stdout is not a tty.
    raw = _keyctl_read_key(keyring_id)
    if raw is not None:
        return _parse_keyctl_read_output(raw)

    KeyringHelper = _get_keyring_helper()
    if KeyringHelper is None:
        raise RuntimeError("Linux keyring helper not available (gr-linux-crypto not installed)")
    helper = KeyringHelper()
    raw_helper = helper.read_key(str(keyring_id))
    return _parse_keyctl_read_output(raw_helper)


def get_shared_secret_from_gnupg(
    my_private_key_pem: bytes,
    peer_public_key_pem: bytes,
) -> bytes:
    """
    Perform ECDH using pre-existing BrainpoolP256r1 keys.
    Keys are loaded from GnuPG keyring externally and passed as PEM.
    """
    CryptoHelpers = _get_crypto_helpers()
    if CryptoHelpers is None:
        raise RuntimeError("CryptoHelpers not available (gr-linux-crypto not installed)")
    crypto = CryptoHelpers()
    private_key = crypto.load_brainpool_private_key(my_private_key_pem)
    public_key = crypto.load_brainpool_public_key(peer_public_key_pem)
    return crypto.brainpool_ecdh(private_key, public_key)


def gdss_nonce(session_id: int, tx_seq: int) -> bytes:
    """12-byte nonce for GDSS ChaCha20 masking stream."""
    return session_id.to_bytes(4, "big") + tx_seq.to_bytes(8, "big")


def payload_nonce(session_id: int, tx_seq: int) -> bytes:
    """96-bit nonce for payload ChaCha20-Poly1305."""
    return b"pay" + session_id.to_bytes(4, "big") + tx_seq.to_bytes(5, "big")

