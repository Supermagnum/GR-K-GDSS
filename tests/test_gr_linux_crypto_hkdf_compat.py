# SPDX-License-Identifier: GPL-3.0-or-later
"""
gr-linux-crypto HKDF compatibility: GDSS masking subkey must match CryptoHelpers.

Ensures derive_session_keys(... )['gdss_masking'] matches gr-linux-crypto
gdss_set_key_source_block default path (salt = 32 zero bytes, info gdss-chacha20-masking-v1).
"""

import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if not os.environ.get("GR_LINUX_CRYPTO_DIR"):
    _sibling = os.path.join(os.path.dirname(REPO_ROOT), "gr-linux-crypto")
    if os.path.isdir(os.path.join(_sibling, "python")):
        os.environ["GR_LINUX_CRYPTO_DIR"] = _sibling

sys.path.insert(0, os.path.join(REPO_ROOT, "python"))

try:
    from session_key_derivation import derive_session_keys  # type: ignore[import-untyped]
except ImportError:
    derive_session_keys = None

try:
    from gr_linux_crypto import CryptoHelpers
except ImportError:
    try:
        from crypto_helpers import CryptoHelpers  # type: ignore[import-untyped]
    except ImportError:
        CryptoHelpers = None

GDSS_MASKING_INFO = b"gdss-chacha20-masking-v1"


@unittest.skipUnless(
    derive_session_keys is not None and CryptoHelpers is not None,
    "derive_session_keys and gr_linux_crypto.CryptoHelpers required",
)
class TestGrLinuxCryptoGdssHkdfCompat(unittest.TestCase):
    def test_gdss_masking_matches_crypto_helpers_derive_key_hkdf(self):
        secret = os.urandom(32)
        k_gdss = derive_session_keys(secret)["gdss_masking"]
        k_crypto = CryptoHelpers.derive_key_hkdf(
            secret,
            salt=bytes(32),
            info=GDSS_MASKING_INFO,
            length=32,
        )
        self.assertEqual(k_gdss, k_crypto)

    def test_longer_ecdh_secret_same_gdss_rule(self):
        secret = os.urandom(48)
        k_gdss = derive_session_keys(secret)["gdss_masking"]
        k_crypto = CryptoHelpers.derive_key_hkdf(
            secret,
            salt=bytes(32),
            info=GDSS_MASKING_INFO,
            length=32,
        )
        self.assertEqual(k_gdss, k_crypto)


if __name__ == "__main__":
    unittest.main()
