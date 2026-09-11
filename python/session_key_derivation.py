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
  - derive_session_keys_from_galdralag(ecdh, epk_i, epk_r, ...) -> same dict via gr-linux-crypto Galdralag KDF
  - map_galdralag_keys_to_kgdss(galdralag_keys, ...) -> map Galdralag dict to gr-k-gdss names
  - galdralag_kdf_available() -> bool
  - store_session_keys(keys) -> dict of name -> keyring ID
  - load_gdss_key(keyring_id) -> 32-byte GDSS masking key
  - gdss_nonce(session_id, tx_seq) -> 12-byte nonce for ChaCha20 masking (session_id may be int or str)
  - allocate_gdss_nonce_counters(key_material, ...) -> (session_id, tx_seq) with persistence
  - reserve_gdss_nonce_counters(key_material, session_id, tx_seq, ...) -> record / refuse reuse
  - default_nonce_state_path() -> path used by the counter helpers
  - gdss_sync_burst_nonce(session_id, burst_index=0) -> 12-byte nonce for sync-burst masking (keystream distinct from data)
  - payload_nonce(session_id, tx_seq) -> 96-bit nonce for payload AEAD
  - get_shared_secret_from_gnupg(my_private_pem, peer_public_pem) -> shared secret
  - keyring_available() -> bool
  - keyring_import_error() -> optional error message

Compatibility with gr-linux-crypto:
  KeyringHelper and CryptoHelpers are imported from gr_linux_crypto when available.
  For GDSS key storage/load, keyctl (keyutils) is required so 32-byte keys are
  stored as raw bytes; KeyringHelper.add_key stores a path, so load_gdss_key
  cannot return key bytes for keys stored that way. See docs/USAGE.md.

  Set environment variable GR_LINUX_CRYPTO_DIR to the top-level path of a
  gr-linux-crypto source checkout so KeyringHelper, CryptoHelpers, and (when
  present) derive_galdralag_session_keys load without a prior make install.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, Type, Union, cast

from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


def _prepend_gr_linux_crypto_python_path() -> None:
    """Insert gr-linux-crypto's python/ on sys.path when GR_LINUX_CRYPTO_DIR is set."""
    root = os.environ.get("GR_LINUX_CRYPTO_DIR")
    if not root:
        return
    python_dir = os.path.join(root, "python")
    if os.path.isdir(python_dir) and python_dir not in sys.path:
        sys.path.insert(0, python_dir)


def _get_keyring_helper() -> Optional[Type[Any]]:
    """
    Lazy import of KeyringHelper from gr-linux-crypto.

    Tries multiple import paths so session_key_derivation loads even when
    gr_linux_crypto is missing. Returns the KeyringHelper class or None.
    """
    import importlib
    _prepend_gr_linux_crypto_python_path()
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
    _prepend_gr_linux_crypto_python_path()
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
    _prepend_gr_linux_crypto_python_path()
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


def _get_derive_galdralag_session_keys() -> Optional[Callable[..., Dict[str, bytes]]]:
    """
    Lazy import of derive_galdralag_session_keys from gr-linux-crypto.

    Matches Galdralag-firmware HKDF labels (see gr-linux-crypto
    python/galdralag_session_kdf.py). Returns None if the installed
    gr-linux-crypto predates that module.
    """
    _prepend_gr_linux_crypto_python_path()
    import importlib

    for import_path in (
        "gr_linux_crypto",
        "gr_linux_crypto.galdralag_session_kdf",
        "galdralag_session_kdf",  # flat python/ tree when GR_LINUX_CRYPTO_DIR/python is on path
    ):
        try:
            mod = importlib.import_module(import_path)
            fn = getattr(mod, "derive_galdralag_session_keys", None)
            if fn is not None:
                return cast(Callable[..., Dict[str, bytes]], fn)
        except ImportError:
            continue
    return None


def galdralag_kdf_available() -> bool:
    """True if gr-linux-crypto exposes derive_galdralag_session_keys (Galdralag-compatible KDF)."""
    return _get_derive_galdralag_session_keys() is not None


def map_galdralag_keys_to_kgdss(
    galdralag_keys: Dict[str, bytes],
    *,
    payload_direction: str = "i2r",
) -> Dict[str, bytes]:
    """
    Map gr-linux-crypto Galdralag session dict to gr-k-gdss derive_session_keys names.

    Galdralag uses payload_key_i2r / payload_key_r2i; gr-k-gdss uses a single
    payload_enc. Choose which payload key feeds payload_enc with payload_direction.

    Args:
        galdralag_keys: Output of derive_galdralag_session_keys from gr-linux-crypto.
        payload_direction: ``i2r`` (initiator to responder) or ``r2i`` (reverse).

    Returns:
        Dict with keys payload_enc, gdss_masking, sync_pn, sync_timing (each 32 bytes).
    """
    if payload_direction not in ("i2r", "r2i"):
        raise ValueError("payload_direction must be 'i2r' or 'r2i'")
    pk = "payload_key_i2r" if payload_direction == "i2r" else "payload_key_r2i"
    need = ("gdss_mask_key", "gdss_sync_key", "gdss_timing_key", pk)
    for name in need:
        if name not in galdralag_keys:
            raise KeyError("galdralag_keys missing {!r}".format(name))
        if len(galdralag_keys[name]) != 32:
            raise ValueError("{!r} must be 32 bytes".format(name))
    return {
        "payload_enc": galdralag_keys[pk],
        "gdss_masking": galdralag_keys["gdss_mask_key"],
        "sync_pn": galdralag_keys["gdss_sync_key"],
        "sync_timing": galdralag_keys["gdss_timing_key"],
    }


def derive_session_keys_from_galdralag(
    ecdh_shared_secret: bytes,
    epk_initiator: bytes,
    epk_responder: bytes,
    *,
    payload_direction: str = "i2r",
) -> Dict[str, bytes]:
    """
    Derive gr-k-gdss session subkeys using gr-linux-crypto's Galdralag KDF.

    Same HKDF labels and salt construction as Galdralag-firmware
    (ephemeral-session crate). Use this when the shared secret and uncompressed
    ephemeral public keys come from a Galdralag/Baochip session exchange.

    Requires a current gr-linux-crypto with python/galdralag_session_kdf.py, or
    GR_LINUX_CRYPTO_DIR pointing at such a source tree.

    Args:
        ecdh_shared_secret: Raw ECDH output (32 / 48 / 64 bytes for Brainpool P256/P384/P512).
        epk_initiator: Initiator ephemeral public key, uncompressed SEC1.
        epk_responder: Responder ephemeral public key, same length as initiator.
        payload_direction: Which Galdralag payload subkey maps to payload_enc (``i2r`` or ``r2i``).

    Returns:
        Same shape as derive_session_keys: payload_enc, gdss_masking, sync_pn, sync_timing.
    """
    fn = _get_derive_galdralag_session_keys()
    if fn is None:
        raise RuntimeError(
            "derive_galdralag_session_keys not found. Install gr-linux-crypto that "
            "includes galdralag_session_kdf, or set GR_LINUX_CRYPTO_DIR to its repository root."
        )
    raw = fn(ecdh_shared_secret, epk_initiator, epk_responder)
    return map_galdralag_keys_to_kgdss(raw, payload_direction=payload_direction)


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


def gdss_nonce(session_id: Union[int, str], tx_seq: int) -> bytes:
    """
    Build the 12-byte nonce for the GDSS ChaCha20 masking keystream.

    Matches the nonce format expected by the C++ spreader/despreader
    (libsodium ChaCha20 IETF: 4-byte session ID + 8-byte TX sequence).

    Args:
        session_id: Numeric session id (big-endian 4 bytes), or an arbitrary string
            label from which a stable 32-bit id is derived (SHA-256).
        tx_seq: Transmission sequence number. Encoded big-endian, 8 bytes.

    Returns:
        12-byte nonce for ChaCha20 IETF (no counter in nonce; counter starts at 0).
    """
    if isinstance(session_id, str):
        digest = hashlib.sha256(f"kgdss-session:{session_id}".encode("utf-8")).digest()
        sid = int.from_bytes(digest[:4], "big")
    else:
        sid = int(session_id)
        if sid < 0 or sid > 0xFFFFFFFF:
            raise ValueError("session_id must fit in an unsigned 32-bit integer")
    if tx_seq < 0 or tx_seq > 0xFFFFFFFFFFFFFFFF:
        raise ValueError("tx_seq must fit in an unsigned 64-bit integer")
    return sid.to_bytes(4, "big") + int(tx_seq).to_bytes(8, "big")

# Reserved tx_seq value so sync-burst mask keystream does not overlap with data.
SYNC_BURST_TX_SEQ = (1 << 64) - 1
# Highest tx_seq that may be issued for data (leave SYNC_BURST_TX_SEQ reserved).
_MAX_DATA_TX_SEQ = SYNC_BURST_TX_SEQ - 1


def default_nonce_state_path() -> str:
    """
    Return the default JSON path for persisted GDSS (session_id, tx_seq) counters.

    Uses ``$XDG_STATE_HOME/gr-k-gdss/nonce_counters.json`` when XDG_STATE_HOME is
    set, otherwise ``~/.local/state/gr-k-gdss/nonce_counters.json``.
    """
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        base = Path(xdg) / "gr-k-gdss"
    else:
        base = Path.home() / ".local" / "state" / "gr-k-gdss"
    return str(base / "nonce_counters.json")


def _gdss_key_fingerprint(key_material: bytes) -> str:
    if len(key_material) < 1:
        raise ValueError("key_material must be non-empty")
    return hashlib.sha256(key_material).hexdigest()


def _load_nonce_state(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {"version": 1, "keys": {}}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "failed to read GDSS nonce state file {!r}: {}".format(str(path), exc)
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError("GDSS nonce state file {!r} is not a JSON object".format(str(path)))
    keys = data.get("keys")
    if keys is None:
        data["keys"] = {}
    elif not isinstance(keys, dict):
        raise RuntimeError("GDSS nonce state file {!r} has invalid 'keys'".format(str(path)))
    data.setdefault("version", 1)
    return data


def _atomic_write_nonce_state(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".nonce_counters.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def allocate_gdss_nonce_counters(
    key_material: bytes,
    *,
    state_path: Optional[str] = None,
    preferred_session_id: int = 1,
) -> Tuple[int, int]:
    """
    Persistently allocate the next unused ``(session_id, tx_seq)`` for a key.

    Counters are keyed by SHA-256 of ``key_material`` (normally the 32-byte
    ``gdss_masking`` key). Each call advances ``tx_seq`` (or ``session_id`` when
    ``tx_seq`` would collide with the reserved sync-burst value) and writes the
    new high-water mark before returning, so process restarts cannot silently
    reuse a prior nonce for the same key.

    Args:
        key_material: Bytes that identify the masking key (e.g. ``gdss_masking``).
        state_path: Optional JSON path; defaults to :func:`default_nonce_state_path`.
        preferred_session_id: Session id used when no prior state exists for this key.

    Returns:
        ``(session_id, tx_seq)`` suitable for :func:`gdss_nonce`. Communicate the
        same pair to the peer receiver out-of-band.
    """
    if preferred_session_id < 0 or preferred_session_id > 0xFFFFFFFF:
        raise ValueError("preferred_session_id must fit in an unsigned 32-bit integer")
    path = Path(state_path) if state_path else Path(default_nonce_state_path())
    fp = _gdss_key_fingerprint(key_material)
    state = _load_nonce_state(path)
    entry = state["keys"].get(fp)
    if entry is None:
        session_id = int(preferred_session_id)
        tx_seq = 1  # never auto-issue tx_seq=0; that value is historically overused
    else:
        session_id = int(entry.get("session_id", preferred_session_id))
        last_tx = int(entry.get("tx_seq", 0))
        if last_tx >= _MAX_DATA_TX_SEQ:
            if session_id >= 0xFFFFFFFF:
                raise RuntimeError(
                    "GDSS nonce counter space exhausted for key fingerprint {}".format(fp[:16])
                )
            session_id += 1
            tx_seq = 1
        else:
            tx_seq = last_tx + 1
    state["keys"][fp] = {"session_id": session_id, "tx_seq": tx_seq}
    _atomic_write_nonce_state(path, state)
    return session_id, tx_seq


def reserve_gdss_nonce_counters(
    key_material: bytes,
    session_id: int,
    tx_seq: int,
    *,
    state_path: Optional[str] = None,
) -> None:
    """
    Record that ``(session_id, tx_seq)`` was used for ``key_material``.

    Raises ``ValueError`` if the pair is not strictly ahead of the stored
    high-water mark (same session with ``tx_seq`` already used or lower, or a
    lower session id). Use this when the operator supplies explicit counters so
    a later :func:`allocate_gdss_nonce_counters` call will not collide.
    """
    if session_id < 0 or session_id > 0xFFFFFFFF:
        raise ValueError("session_id must fit in an unsigned 32-bit integer")
    if tx_seq < 0 or tx_seq > _MAX_DATA_TX_SEQ:
        raise ValueError(
            "tx_seq must be in [0, 2**64-2]; 2**64-1 is reserved for sync-burst masking"
        )
    path = Path(state_path) if state_path else Path(default_nonce_state_path())
    fp = _gdss_key_fingerprint(key_material)
    state = _load_nonce_state(path)
    entry = state["keys"].get(fp)
    if entry is not None:
        prev_sid = int(entry.get("session_id", 0))
        prev_tx = int(entry.get("tx_seq", -1))
        if session_id < prev_sid or (session_id == prev_sid and tx_seq <= prev_tx):
            raise ValueError(
                "refusing to reuse GDSS (session_id, tx_seq)=({}, {}) for this key; "
                "last recorded was ({}, {}). Allocate a fresh pair with "
                "allocate_gdss_nonce_counters() or choose a strictly greater counter.".format(
                    session_id, tx_seq, prev_sid, prev_tx
                )
            )
    state["keys"][fp] = {"session_id": int(session_id), "tx_seq": int(tx_seq)}
    _atomic_write_nonce_state(path, state)


def gdss_sync_burst_nonce(session_id: int, burst_index: int = 0) -> bytes:
    """
    Return the 12-byte nonce for sync-burst keyed Gaussian masking.

    Use this (with gdss_masking key) when calling apply_keyed_gaussian_mask
    so the sync burst keystream is distinct from the data keystream. Same
    session_id as the link; ``tx_seq`` is taken from the reserved high end of
    the counter space (``SYNC_BURST_TX_SEQ - burst_index``) so each scheduled
    burst gets a distinct nonce. Default ``burst_index=0`` preserves the
    historical single-burst nonce (``tx_seq == SYNC_BURST_TX_SEQ``).

    Args:
        session_id: Session identifier.
        burst_index: Index within the sync schedule (must be >= 0).

    Returns:
        12-byte nonce for ChaCha20 IETF.
    """
    if burst_index < 0:
        raise ValueError("burst_index must be >= 0")
    if burst_index > _MAX_DATA_TX_SEQ:
        raise ValueError("burst_index exceeds reserved sync-burst nonce space")
    return gdss_nonce(session_id, SYNC_BURST_TX_SEQ - int(burst_index))


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
