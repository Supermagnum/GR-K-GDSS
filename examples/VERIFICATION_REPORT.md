# Verification Report: tx_example_kgdss.grc

Verification steps run against `tx_example_kgdss.grc` in this directory.

## Verification procedure (three layers)

Run from the `examples/` directory:

1. **Step 1 — YAML syntax:**  
   `python3 -c "import yaml; yaml.safe_load(open('tx_example_kgdss.grc'))"`  
   Confirm it parses without error.

2. **Step 2b — Generate Python with grcc:**  
   `grcc tx_example_kgdss.grc`  
   Confirm it exits without errors and produces `tx_example_kgdss.py`. Block or connection errors surface here.

3. **Step 2c — Python syntax check on generated file:**  
   `python3 -m py_compile tx_example_kgdss.py`  
   Confirms the generated Python is syntactically valid before running the flowgraph.

These three steps (YAML parse, grcc compilation, Python syntax) catch most errors before runtime. Optionally run the full checker: `python3 verify_tx_example_kgdss.py`.

---

## Step 1 — XML/YAML syntax check

**Result: PASS**

Command run:
```bash
python3 -c "import yaml; yaml.safe_load(open('tx_example_kgdss.grc'))"
```
Parses without error.

---

## Step 2b — Generate Python with grcc

**Result: PASS**

Command run:
```bash
grcc tx_example_kgdss.grc
```
Exits without errors and produces `tx_example_kgdss.py`. Block and connection errors surface at this stage.

---

## Step 2c — Python syntax check on generated file

**Result: PASS**

Command run:
```bash
python3 -m py_compile tx_example_kgdss.py
```
The generated Python is syntactically valid.

---

## Step 2 — Block name uniqueness

**Result: PASS**

Within the flowgraph, every block is identified by its **name** (instance identifier). All such names are unique. Block **id** (block type) may repeat by design (e.g. six `variable` blocks).

**Block names (instance identifiers):**
- sample_rate
- session_id
- tx_seq
- keyring_id
- key_store_path
- callsigns
- audio_source_0
- rational_resampler_xxx_0
- blocks_float_to_short_0
- vocoder_codec2_encode_sp_0
- blocks_vector_to_stream_0
- brainpool_ecies_multi_encrypt_0
- blocks_unpack_k_bits_bb_0
- qradiolink_mod_soqpsk_0
- kgdss_key_injector_0
- kgdss_spreader_cc_0
- blocks_null_sink_0

**Block types (id):** variable (x6), audio_source, rational_resampler_xxx, blocks_float_to_short, vocoder_codec2_encode_sp, blocks_vector_to_stream, brainpool_ecies_multi_encrypt, blocks_unpack_k_bits_bb, qradiolink_mod_soqpsk, kgdss_key_injector, kgdss_spreader_cc, blocks_null_sink

No duplicate block names. Duplicates: none.

---

## Step 3 — Connection integrity check

**Result: PASS**

For every connection `[source_name, src_port, dest_name, dst_port]`:

- The source block name exists in the block list.
- The destination block name exists in the block list.
- Stream connections use port values `'0'` (non-negative integer).
- The single message connection uses port name `set_key` on both ends (GRC uses port label for message ports).

**Connections:**
| # | Source | Src port | Destination | Dst port |
|---|--------|----------|-------------|----------|
| 1 | audio_source_0 | 0 | rational_resampler_xxx_0 | 0 |
| 2 | rational_resampler_xxx_0 | 0 | blocks_float_to_short_0 | 0 |
| 3 | blocks_float_to_short_0 | 0 | vocoder_codec2_encode_sp_0 | 0 |
| 4 | vocoder_codec2_encode_sp_0 | 0 | blocks_vector_to_stream_0 | 0 |
| 5 | blocks_vector_to_stream_0 | 0 | brainpool_ecies_multi_encrypt_0 | 0 |
| 6 | brainpool_ecies_multi_encrypt_0 | 0 | blocks_unpack_k_bits_bb_0 | 0 |
| 7 | blocks_unpack_k_bits_bb_0 | 0 | qradiolink_mod_soqpsk_0 | 0 |
| 8 | qradiolink_mod_soqpsk_0 | 0 | kgdss_spreader_cc_0 | 0 |
| 9 | kgdss_spreader_cc_0 | 0 | blocks_null_sink_0 | 0 |
| 10 | kgdss_key_injector_0 | set_key | kgdss_spreader_cc_0 | set_key |

Broken connections: none.

---

## Step 4 — Message port connection check

**Result: PASS**

Single message connection: `kgdss_key_injector_0` port `set_key` -> `kgdss_spreader_cc_0` port `set_key`.

GRC uses the port **label** as the connection key for message ports (not the port id). The key_injector output has label `set_key`; the spreader message input has id/label `set_key`.

- Source block exists: kgdss_key_injector_0 (type kgdss_key_injector).
- Destination block exists: kgdss_spreader_cc_0 (type kgdss_spreader_cc).
- Source port `set_key`: matches output label in `grc/kgdss_key_injector.block.yml` (outputs: id key_out, label set_key).
- Destination port `set_key`: matches message input in `grc/kgdss_spreader_cc.block.yml` (inputs: stream 0, message set_key).

Unconfirmed message ports: none.

---

## Step 5 — Cross-check against encrypt_decrypt example

**Comparison:**

- The **encrypt_decrypt** example (`gr-linux-crypto/examples/encrypt_decrypt/freedv_nitrokey_encryption.grc`) does **not** use a Brainpool ECIES block. It uses:
  - `linux_crypto_nitrokey_interface` for key material
  - An `epy_block` for ChaCha20-Poly1305 encryption
  - Same chain style: Audio Source -> resampler -> float_to_short -> Codec2 encode -> encryptor -> (in their case FreeDV TX, in ours unpack -> SOQPSK -> GDSS spreader -> null sink).

- **tx_example_kgdss.grc** uses:
  - `brainpool_ecies_multi_encrypt` (gr-linux-crypto) for encryption, with parameters:
    - curve: `"brainpoolP256r1"`
    - callsigns: variable `callsigns`
    - key_store_path: variable `key_store_path`
    - kdf_info: `"gr-linux-crypto-ecies-v1"`
  - Connection style matches: same YAML list format `[src_name, src_port, dst_name, dst_port]`.
  - Parameter style matches: block parameters reference variable block names (e.g. `callsigns`, `key_store_path`) like encrypt_decrypt uses `nitrokey_slot`, `samp_rate`.

**Intentional differences:**

- Use of **Brainpool ECIES Multi-Recipient** instead of Nitrokey + epy_block is by design (ECDH/ECIES for this example).
- Brainpool block parameters and connection pattern match `gr-linux-crypto/grc/brainpool_ecies_multi_encrypt.block.yml`.

**Conclusion:** Matched where applicable; remaining differences are intentional (different encryption path and blocks).

---

## Step 6 — Summary

| Check | Result |
|-------|--------|
| YAML syntax | **PASS** |
| grcc generation (Step 2b) | **PASS** |
| Python syntax on generated file (Step 2c) | **PASS** |
| Block name uniqueness | **PASS** (no duplicates) |
| Connection integrity | **PASS** (no broken connections) |
| Message port connections | **PASS** (no unconfirmed ports) |
| Brainpool cross-check | **Matched** (parameters and style consistent; differences intentional) |

**File status: READY.** All checks pass. Three layers of verification: YAML parse, grcc compilation, and Python syntax.
