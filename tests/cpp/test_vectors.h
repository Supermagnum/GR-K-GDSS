/*
 * Hardcoded ChaCha20-IETF / RFC test material for kgdss crypto tests.
 *
 * Lineage (for auditors):
 * - BSI TR-02102-1 does not define its own ChaCha20 byte vectors; it references RFC 7539
 *   and NIST SP 800-38D family documents. The vectors below are taken from RFC 7539 and
 *   NIST-aligned AEAD examples, cited by section.
 * - RFC 7539 Section 2.1.1 illustrates the ChaCha20 block function; the 64-byte sequence
 *   here is bytes [64, 128) of the libsodium/crypto_stream_chacha20_ietf keystream for
 *   key and nonce all zero (i.e. the second 64-byte block, IETF block counter 1).
 * - RFC 7539 Section 2.4.2 gives the AEAD example; message XOR ciphertext equals the
 *   ChaCha20 keystream applied to the message bytes starting at byte offset 64 in the
 *   same IETF stream (first 64 bytes are consumed by the Poly1305 key derivation step).
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifndef KGDSS_TEST_TEST_VECTORS_H
#define KGDSS_TEST_TEST_VECTORS_H

#include <cstddef>

/* RFC 7539 Section 2.1.1 — all-zero 32-byte key, 12-byte zero nonce; first 64 bytes of
 * keystream at IETF block counter 1 (stream byte indices 64..127 inclusive). */
static const char RFC7539_2_1_1_KEYSTREAM_BLOCK1_HEX[] =
    "9f07e7be5551387a98ba977c732d080dcb0f29a048e3656912c6533e32ee7aed"
    "29b721769ce64e43d57133b074d839d531ed1f28510afb45ace10a1f4b794d6f";

/* RFC 7539 Section 2.4.2 — key / nonce / plaintext / ciphertext (tag excluded from ct
 * hex here: only the encrypted payload, 114 bytes). */
static const char RFC7539_2_4_2_KEY_HEX[] =
    "808182838485868788898a8b8c8d8e8f909192939495969798999a9b9c9d9e9f";
static const char RFC7539_2_4_2_NONCE_HEX[] = "070000004041424344454647";
static const char RFC7539_2_4_2_MSG_HEX[] =
    "4c616469657320616e642047656e746c656d656e206f662074686520636c617373206f66202739"
    "393a204966204920636f756c64206f6666657220796f75206f6e6c79206f6e65207469702066"
    "6f7220746865206675747572652c2073756e73637265656e20776f756c642062652069742e";
static const char RFC7539_2_4_2_CT_HEX[] =
    "d31a8d34648e60db7b86afbc53ef7ec2a4aded51296e08fea9e2b5a736ee62d63dbea45e8ca96"
    "71282fafb69da92728b1a71de0a9e060b2905d6a5b67ecd3b3692ddbd7f2d778b8c9803aee32"
    "8091b58fab324e4fad675945585808b4831d7bc3ff4def08e4b7a9de576d26586cec64b6116";

static constexpr size_t RFC7539_2_4_2_MSG_LEN = 114;

#endif
