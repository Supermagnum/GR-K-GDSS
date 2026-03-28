# SPDX-License-Identifier: GPL-3.0-or-later
"""
Galdralag KDF (gr-linux-crypto) mapped to gr-k-gdss session key names.

Skips when gr-linux-crypto does not provide galdralag_session_kdf.
Set GR_LINUX_CRYPTO_DIR to a gr-linux-crypto repository root to test against a source tree.
"""

import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "python"))

if not os.environ.get("GR_LINUX_CRYPTO_DIR"):
    _sibling = os.path.join(os.path.dirname(REPO_ROOT), "gr-linux-crypto")
    if os.path.isdir(os.path.join(_sibling, "python")):
        os.environ["GR_LINUX_CRYPTO_DIR"] = _sibling

from session_key_derivation import (  # type: ignore[import-untyped]
    derive_session_keys_from_galdralag,
    galdralag_kdf_available,
    map_galdralag_keys_to_kgdss,
)


@unittest.skipUnless(
    galdralag_kdf_available(),
    "gr-linux-crypto galdralag_session_kdf not available (install gr-linux-crypto or set GR_LINUX_CRYPTO_DIR)",
)
class TestGaldralagKgdssMapping(unittest.TestCase):
    def test_derive_produces_four_named_keys(self):
        ikm = bytes(range(32))
        epk_i = b"\x04" + b"\xaa" * 64
        epk_r = b"\x04" + b"\x55" * 64
        d = derive_session_keys_from_galdralag(ikm, epk_i, epk_r)
        self.assertEqual(
            set(d.keys()), {"payload_enc", "gdss_masking", "sync_pn", "sync_timing"}
        )
        for name, val in d.items():
            self.assertEqual(len(val), 32, name)

    def test_payload_direction_r2i_differs_from_i2r(self):
        ikm = bytes(range(32))
        epk_i = b"\x04" + b"\xaa" * 64
        epk_r = b"\x04" + b"\x55" * 64
        a = derive_session_keys_from_galdralag(ikm, epk_i, epk_r, payload_direction="i2r")
        b = derive_session_keys_from_galdralag(ikm, epk_i, epk_r, payload_direction="r2i")
        self.assertEqual(a["gdss_masking"], b["gdss_masking"])
        self.assertNotEqual(a["payload_enc"], b["payload_enc"])

    def test_swap_epk_same_gdss_keys(self):
        ikm = bytes(range(32))
        epk_a = b"\x04" + b"\x03" * 64
        epk_b = b"\x04" + b"\xcc" * 64
        k1 = derive_session_keys_from_galdralag(ikm, epk_a, epk_b)
        k2 = derive_session_keys_from_galdralag(ikm, epk_b, epk_a)
        self.assertEqual(k1["gdss_masking"], k2["gdss_masking"])
        self.assertEqual(k1["sync_pn"], k2["sync_pn"])
        self.assertEqual(k1["sync_timing"], k2["sync_timing"])

    def test_map_invalid_payload_direction(self):
        fake = {
            "payload_key_i2r": b"\x00" * 32,
            "payload_key_r2i": b"\x01" * 32,
            "gdss_mask_key": b"\x02" * 32,
            "gdss_sync_key": b"\x03" * 32,
            "gdss_timing_key": b"\x04" * 32,
        }
        with self.assertRaises(ValueError):
            map_galdralag_keys_to_kgdss(fake, payload_direction="x")


if __name__ == "__main__":
    unittest.main()
