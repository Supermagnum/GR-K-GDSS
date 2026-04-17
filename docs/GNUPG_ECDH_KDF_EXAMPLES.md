# GnuPG ECDH Session Key Derivation (Coding-Focused)

This note is for developers who are comfortable with code, but are new to GnuPG-based encryption workflows.

It explains how GR-K-GDSS derives session keys from pre-existing GnuPG keys, with concrete example values and byte/bit layouts.

---

## What Happens At Session Start

The key is derived from a BrainpoolP256r1 Elliptic Curve Diffie-Hellman (ECDH) key exchange using pre-existing GnuPG keys.

Both peers exchange public keys off-air (for example through the GnuPG web of trust), then compute the same shared secret locally:

- Transmitter: own private key + receiver public key -> ECDH shared secret
- Receiver: own private key + transmitter public key -> ECDH shared secret

No shared secret is transmitted over RF.

That shared secret is then expanded with HKDF-SHA256 (RFC 5869) using domain separation.

---

## Four Derived 32-Byte Subkeys

From one ECDH shared secret, `derive_session_keys()` outputs four independent 32-byte keys:

| Subkey | Purpose |
|---|---|
| Key 1 (`payload_enc`) | ChaCha20-Poly1305 payload encryption |
| Key 2 (`gdss_masking`) | ChaCha20 GDSS masking keystream |
| Key 3 (`sync_pn`) | Sync burst PN sequence |
| Key 4 (`sync_timing`) | Sync burst timing offset schedule |

Domain-separation labels used in code:

- `payload-chacha20poly1305-v1`
- `gdss-chacha20-masking-v1`
- `sync-dsss-pn-sequence-v1`
- `sync-burst-timing-offset-v1`

---

## Example Values

The values below are illustrative examples with realistic sizes and formats.

### Example ECDH Shared Secret (32 bytes)

Hex (64 chars):

`9f6b4b0a5d2c22f134915a1d785fd31de6a76d98c8ce2f67c9f5a1d3be9098ab`

As raw bytes:

```text
9f 6b 4b 0a 5d 2c 22 f1 34 91 5a 1d 78 5f d3 1d
e6 a7 6d 98 c8 ce 2f 67 c9 f5 a1 d3 be 90 98 ab
```

First 8 bytes as bitstring:

```text
10011111 01101011 01001011 00001010 01011101 00101100 00100010 11110001
```

### Example Derived Subkeys (all 32 bytes each)

Example format only (values shown as hex):

- `payload_enc`:
  `2d8db8d55f7cd8b6e4f2da4fd16b47d1114ef3a3f9f5b2a2d4797b8a8d1f5c44`
- `gdss_masking`:
  `cb7f2e7fdfb879a7478f76071dc9ba5fd236f3ab4f6df73b34634af57f4cc6d2`
- `sync_pn`:
  `a11a20ce4ff95ec34919035994621962fd71f89f47ca8f8361f3e57eecf37b0a`
- `sync_timing`:
  `4b8c5a3a9033c275f667645b6c33f005f49f676f96f4c93a55d7f9c5f65d18de`

---

## Nonce Layout Used By GDSS Masking

`gdss_nonce(session_id, tx_seq)` returns 12 bytes:

- 4-byte `session_id` (big-endian)
- 8-byte `tx_seq` (big-endian)

Example:

- `session_id = 0x0000002A` (42)
- `tx_seq = 0x0000000000000015` (21)

Nonce bytes:

```text
00 00 00 2a 00 00 00 00 00 00 00 15
```

Bit layout:

```text
session_id: 00000000 00000000 00000000 00101010
tx_seq:     00000000 00000000 00000000 00000000 00000000 00000000 00000000 00010101
```

---

## Minimal Python Example

```python
from gnuradio import kgdss

# 32-byte ECDH shared secret from BrainpoolP256r1 exchange
shared_secret = bytes.fromhex(
    "9f6b4b0a5d2c22f134915a1d785fd31de6a76d98c8ce2f67c9f5a1d3be9098ab"
)

keys = kgdss.derive_session_keys(shared_secret)

payload_enc = keys["payload_enc"]      # Key 1
gdss_masking = keys["gdss_masking"]    # Key 2
sync_pn = keys["sync_pn"]              # Key 3
sync_timing = keys["sync_timing"]      # Key 4

nonce = kgdss.gdss_nonce(session_id=42, tx_seq=21)
```

---

## Important Security Notes

- Never reuse the same `(gdss_masking key, nonce)` pair across sessions.
- Keep private keys and shared secrets off logs and telemetry.
- Public-key exchange authenticity still matters; web-of-trust validation is part of the threat model.

