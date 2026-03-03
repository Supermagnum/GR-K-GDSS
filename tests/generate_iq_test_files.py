#!/usr/bin/env python3
"""
Generate IQ test files for validating gr-k-gdss keyed GDSS blocks.
All outputs are float32 interleaved IQ (complex64). Requires: numpy, scipy, cryptography.
For ChaCha20 matching libsodium IETF, pycryptodome is used if available; else cryptography.
"""

import json
import math
import os
import struct
import sys

import numpy as np
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

# Try PyCryptodome for ChaCha20 (12-byte nonce, matches libsodium IETF)
try:
    from Crypto.Cipher import ChaCha20 as PyChaCha20
    _CHACHA20_BACKEND = "pycryptodome"
except ImportError:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
    from cryptography.hazmat.backends import default_backend as _default_backend
    _CHACHA20_BACKEND = "cryptography"

# Fixed parameters (reproducible tests)
SAMPLE_RATE = 500_000
DURATION_SEC = 10
N_SAMPLES = SAMPLE_RATE * DURATION_SEC  # 5,000,000
SPREADING_N = 256

TEST_KEY = bytes(range(32))
TEST_NONCE = bytes(range(12))
WRONG_KEY = bytes([x ^ 0xFF for x in range(32)])
WRONG_NONCE = bytes([x ^ 0xFF for x in range(12)])
TEST_SHARED_SECRET = bytes(range(32))
SESSION_ID = 1
TX_SEQ = 0
PAYLOAD_BYTES = bytes([i % 256 for i in range(1024)])
RNG_SEED = 42
VARIANCE = 1.0
MIN_MASK = 1e-4

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iq_files")


def _derive_session_keys(ecdh_shared_secret: bytes, salt: bytes = None):
    """HKDF-based session key derivation (matches session_key_derivation.py)."""
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
        "gdss_masking": hkdf_expand(b"gdss-chacha20-masking-v1"),
    }


def _gdss_nonce(session_id: int, tx_seq: int) -> bytes:
    return session_id.to_bytes(4, "big") + tx_seq.to_bytes(8, "big")


def _chacha20_keystream(key: bytes, nonce: bytes, num_bytes: int) -> bytes:
    """Generate ChaCha20 IETF keystream (match libsodium crypto_stream_chacha20_ietf)."""
    if _CHACHA20_BACKEND == "pycryptodome":
        cipher = PyChaCha20.new(key=key, nonce=nonce)
        return cipher.encrypt(b"\x00" * num_bytes)
    # cryptography: 16-byte nonce = counter (4 bytes LE) + nonce (12 bytes)
    nonce_16 = struct.pack("<I", 0) + nonce
    cipher = Cipher(
        algorithms.ChaCha20(key, nonce_16),
        mode=None,
        backend=_default_backend(),
    )
    encryptor = cipher.encryptor()
    out = b""
    chunk = 1024 * 1024  # 1 MB chunks
    while len(out) < num_bytes:
        n = min(chunk, num_bytes - len(out))
        out += encryptor.update(b"\x00" * n)
    return out[:num_bytes]


def _to_uniform(b: bytes) -> float:
    """Four bytes to uniform [0,1) (match C++ memcpy uint32 LE)."""
    v = struct.unpack("<I", b[:4])[0]
    return (float(v) + 0.5) / 4294967296.0


def _box_muller(u1: float, u2: float, variance: float = VARIANCE) -> float:
    """Box-Muller transform matching kgdss_spreader_cc_impl.cc (with variance)."""
    if u1 < 1e-10:
        u1 = 1e-10
    g = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return g * math.sqrt(variance)


def _fill_masks(keystream: bytes, n_chips: int, variance: float = VARIANCE):
    """Yield (mask_i, mask_q) per chip from keystream (16 bytes per chip)."""
    for i in range(n_chips):
        base = i * 16
        u1 = _to_uniform(keystream[base : base + 4])
        u2 = _to_uniform(keystream[base + 4 : base + 8])
        u3 = _to_uniform(keystream[base + 8 : base + 12])
        u4 = _to_uniform(keystream[base + 12 : base + 16])
        mask_i = _box_muller(u1, u2, variance)
        mask_q = _box_muller(u3, u4, variance)
        if abs(mask_i) < MIN_MASK:
            mask_i = MIN_MASK if mask_i >= 0 else -MIN_MASK
        if abs(mask_q) < MIN_MASK:
            mask_q = MIN_MASK if mask_q >= 0 else -MIN_MASK
        yield (mask_i, mask_q)


def _masks_array(keystream: bytes, n_chips: int, variance: float = VARIANCE) -> np.ndarray:
    """Vectorized: (n_chips, 2) array of (mask_i, mask_q) per chip. Clamp to MIN_MASK."""
    ks = np.frombuffer(keystream[: n_chips * 16], dtype=np.uint8)
    ks = ks.reshape(-1, 16)
    v = np.frombuffer(ks[:, :4].tobytes(), dtype="<u4")
    u1 = (v.astype(np.float64) + 0.5) / 4294967296.0
    v = np.frombuffer(ks[:, 4:8].tobytes(), dtype="<u4")
    u2 = (v.astype(np.float64) + 0.5) / 4294967296.0
    v = np.frombuffer(ks[:, 8:12].tobytes(), dtype="<u4")
    u3 = (v.astype(np.float64) + 0.5) / 4294967296.0
    v = np.frombuffer(ks[:, 12:16].tobytes(), dtype="<u4")
    u4 = (v.astype(np.float64) + 0.5) / 4294967296.0
    u1 = np.maximum(u1, 1e-10)
    g_i = np.sqrt(-2.0 * np.log(u1)) * np.cos(2.0 * np.pi * u2) * np.sqrt(variance)
    g_q = np.sqrt(-2.0 * np.log(u3)) * np.cos(2.0 * np.pi * u4) * np.sqrt(variance)
    mask_i = np.where(np.abs(g_i) < MIN_MASK, np.where(g_i >= 0, MIN_MASK, -MIN_MASK), g_i)
    mask_q = np.where(np.abs(g_q) < MIN_MASK, np.where(g_q >= 0, MIN_MASK, -MIN_MASK), g_q)
    return np.column_stack([mask_i, mask_q])


def _derive_sync_pn_sequence(master_key: bytes, session_id: int, chips: int) -> np.ndarray:
    """PN sequence matching sync_burst_utils.derive_sync_pn_sequence (using cryptography ChaCha20)."""
    import hmac
    import hashlib
    pn_key = hmac.new(
        master_key,
        b"sync-pn-v1" + session_id.to_bytes(8, "big"),
        hashlib.sha256,
    ).digest()
    nonce_12 = b"\x00" * 12
    raw_len = chips // 8 + 1
    if _CHACHA20_BACKEND == "pycryptodome":
        cipher = PyChaCha20.new(key=pn_key, nonce=nonce_12)
        raw = cipher.encrypt(b"\x00" * raw_len)
    else:
        nonce_16 = struct.pack("<I", 0) + nonce_12
        cipher = Cipher(
            algorithms.ChaCha20(pn_key, nonce_16),
            mode=None,
            backend=_default_backend(),
        )
        raw = cipher.encryptor().update(b"\x00" * raw_len)
    bits = np.unpackbits(np.frombuffer(raw[: (raw_len + 7) // 8 * 8], dtype=np.uint8))[:chips]
    return bits.astype(np.float32) * 2 - 1


def _gaussian_envelope(samples: np.ndarray, rise_fraction: float = 0.1) -> np.ndarray:
    """Match sync_burst_utils.gaussian_envelope."""
    n = len(samples)
    env = np.ones(n, dtype=np.float32)
    flank = int(n * rise_fraction)
    if flank > 0:
        x = np.linspace(-3, 0, flank, dtype=np.float32)
        ramp = np.exp(-(x**2) / 2)
        ramp = ramp / ramp[-1]
        env[:flank] = ramp
        env[-flank:] = ramp[::-1]
    return samples * env


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # File 1 - Gaussian noise baseline
    rng = np.random.default_rng(seed=RNG_SEED)
    noise = (rng.standard_normal(N_SAMPLES) + 1j * rng.standard_normal(N_SAMPLES)).astype(np.complex64)
    noise.tofile(os.path.join(OUTPUT_DIR, "01_gaussian_noise_baseline.cf32"))
    from scipy import stats
    I, Q = noise.real, noise.imag
    meta1 = {
        "mean_i": float(np.mean(I)),
        "mean_q": float(np.mean(Q)),
        "std_i": float(np.std(I)),
        "std_q": float(np.std(Q)),
        "kurtosis_i": float(stats.kurtosis(I, fisher=False)),
        "kurtosis_q": float(stats.kurtosis(Q, fisher=False)),
    }
    with open(os.path.join(OUTPUT_DIR, "01_gaussian_noise_baseline.json"), "w") as f:
        json.dump(meta1, f, indent=2)

    # File 2 - Plaintext reference (BPSK)
    bits = np.unpackbits(np.frombuffer(PAYLOAD_BYTES, dtype=np.uint8))
    symbols_bpsk = (2.0 * bits.astype(np.float32) - 1.0) + 0.0j
    n_sym = len(symbols_bpsk)
    repeat = (N_SAMPLES + n_sym - 1) // n_sym
    plaintext = np.tile(symbols_bpsk, repeat)[:N_SAMPLES].astype(np.complex64)
    plaintext.tofile(os.path.join(OUTPUT_DIR, "02_plaintext_reference.cf32"))
    with open(os.path.join(OUTPUT_DIR, "02_payload_reference.bin"), "wb") as f:
        f.write(PAYLOAD_BYTES)

    # File 3 - Keyed GDSS transmission (correct key)
    keys = _derive_session_keys(TEST_SHARED_SECRET)
    gdss_key = keys["gdss_masking"]
    nonce = _gdss_nonce(SESSION_ID, TX_SEQ)
    n_symbols = (N_SAMPLES + SPREADING_N - 1) // SPREADING_N
    n_chips = n_symbols * SPREADING_N
    ks_len = n_chips * 16
    keystream = _chacha20_keystream(gdss_key, nonce, ks_len)
    symbols_in = np.tile(symbols_bpsk, (n_symbols // n_sym + 1))[:n_symbols]
    masks = _masks_array(keystream, n_chips)
    symbols_expanded = np.repeat(symbols_in, SPREADING_N)
    chips_out = (symbols_expanded.real * masks[:, 0] + 1j * symbols_expanded.imag * masks[:, 1]).astype(np.complex64)
    if n_chips < N_SAMPLES:
        pad = np.zeros(N_SAMPLES - n_chips, dtype=np.complex64)
        transmission = np.concatenate([chips_out, pad])
    else:
        transmission = chips_out[:N_SAMPLES]
    transmission.tofile(os.path.join(OUTPUT_DIR, "03_keyed_gdss_transmission.cf32"))
    I3, Q3 = transmission.real, transmission.imag
    meta3 = {
        "key_hex": gdss_key.hex(),
        "nonce_hex": nonce.hex(),
        "session_id": SESSION_ID,
        "tx_seq": TX_SEQ,
        "spreading_factor": SPREADING_N,
        "mean_i": float(np.mean(I3)),
        "mean_q": float(np.mean(Q3)),
        "std_i": float(np.std(I3)),
        "std_q": float(np.std(Q3)),
        "kurtosis_i": float(stats.kurtosis(I3, fisher=False)),
        "kurtosis_q": float(stats.kurtosis(Q3, fisher=False)),
    }
    with open(os.path.join(OUTPUT_DIR, "03_keyed_gdss_transmission.json"), "w") as f:
        json.dump(meta3, f, indent=2)

    # File 4 - Correct-key despread (round-trip)
    masks4 = _masks_array(_chacha20_keystream(gdss_key, nonce, n_chips * 16), n_chips)
    unmask_i = (chips_out.real / masks4[:, 0]).reshape(n_symbols, SPREADING_N).mean(axis=1)
    unmask_q = (chips_out.imag / masks4[:, 1]).reshape(n_symbols, SPREADING_N).mean(axis=1)
    recovered = (unmask_i + 1j * unmask_q).astype(np.complex64)
    orig_sym = symbols_in[:n_symbols].real
    rec_sym = recovered.real
    if n_symbols < N_SAMPLES:
        pad4 = np.zeros(N_SAMPLES - n_symbols, dtype=np.complex64)
        despread_out = np.concatenate([recovered, pad4])
    else:
        despread_out = np.zeros(N_SAMPLES, dtype=np.complex64)
        despread_out[:n_symbols] = recovered
    despread_out.tofile(os.path.join(OUTPUT_DIR, "04_keyed_gdss_despread_correct_key.cf32"))
    corr4 = np.corrcoef(orig_sym.flatten(), rec_sym.flatten())[0, 1] if len(orig_sym) > 1 else 1.0
    with open(os.path.join(OUTPUT_DIR, "04_keyed_gdss_despread_correct_key.json"), "w") as f:
        json.dump({"pearson_correlation_vs_payload": float(corr4)}, f, indent=2)
    assert corr4 > 0.95, f"Round-trip correlation {corr4} <= 0.95"

    # File 5 - Wrong-key despread
    masks5 = _masks_array(_chacha20_keystream(WRONG_KEY, WRONG_NONCE, n_chips * 16), n_chips)
    unmask_i5 = (chips_out.real / masks5[:, 0]).reshape(n_symbols, SPREADING_N).mean(axis=1)
    unmask_q5 = (chips_out.imag / masks5[:, 1]).reshape(n_symbols, SPREADING_N).mean(axis=1)
    recovered5 = (unmask_i5 + 1j * unmask_q5).astype(np.complex64)
    rec5 = recovered5.real
    corr5 = np.corrcoef(orig_sym.flatten(), rec5.flatten())[0, 1] if len(orig_sym) > 1 else 0.0
    if n_symbols < N_SAMPLES:
        pad5 = np.zeros(N_SAMPLES - n_symbols, dtype=np.complex64)
        wrong_out = np.concatenate([recovered5, pad5])
    else:
        wrong_out = np.zeros(N_SAMPLES, dtype=np.complex64)
        wrong_out[:n_symbols] = recovered5
    wrong_out.tofile(os.path.join(OUTPUT_DIR, "05_keyed_gdss_despread_wrong_key.cf32"))
    with open(os.path.join(OUTPUT_DIR, "05_keyed_gdss_despread_wrong_key.json"), "w") as f:
        json.dump({"pearson_correlation_vs_payload": float(corr5)}, f, indent=2)
    assert abs(corr5) < 0.05, f"Wrong-key correlation |{corr5}| >= 0.05"

    # File 6 - Sync burst isolation
    burst_len = 1000  # 2 ms at 500 kHz
    silence_half = 250_000  # 0.5 s
    total_6 = silence_half * 2 + burst_len
    pn = _derive_sync_pn_sequence(TEST_SHARED_SECRET, SESSION_ID, burst_len)
    burst_raw = pn.astype(np.complex64)
    burst_envelope = _gaussian_envelope(burst_raw, rise_fraction=0.1)
    noise_floor = 1.0
    peak_target_db = 4.5
    scale = noise_floor * (10 ** (peak_target_db / 20.0)) / (np.max(np.abs(burst_envelope)) + 1e-12)
    burst_scaled = burst_envelope * scale
    silence = np.zeros(silence_half, dtype=np.complex64)
    burst_silence = np.zeros(burst_len, dtype=np.complex64)
    file6 = np.concatenate([silence, burst_scaled, silence])
    if len(file6) < N_SAMPLES:
        file6 = np.concatenate([file6, np.zeros(N_SAMPLES - len(file6), dtype=np.complex64)])
    else:
        file6 = file6[:N_SAMPLES]
    file6.tofile(os.path.join(OUTPUT_DIR, "06_sync_burst_isolation.cf32"))
    burst_power = np.mean(np.abs(burst_scaled) ** 2)
    meta6 = {
        "burst_duration_ms": 2.0,
        "burst_power_db_above_noise": peak_target_db,
        "noise_floor_power": float(noise_floor**2),
        "burst_peak_power": float(np.max(np.abs(burst_scaled)) ** 2),
    }
    with open(os.path.join(OUTPUT_DIR, "06_sync_burst_isolation.json"), "w") as f:
        json.dump(meta6, f, indent=2)

    # Files 7A, 7B - Nonce reuse
    payload_a = symbols_bpsk
    payload_b = (2.0 * (1 - bits.astype(np.float32)) - 1.0) + 0.0j
    n_sym7 = (N_SAMPLES + SPREADING_N - 1) // SPREADING_N
    n_chips7 = n_sym7 * SPREADING_N
    ks7 = _chacha20_keystream(gdss_key, nonce, n_chips7 * 16)
    masks7 = _masks_array(ks7, n_chips7)
    sym_rep_a = np.tile(payload_a, (n_sym7 // len(payload_a) + 1))[:n_sym7]
    sym_rep_b = np.tile(payload_b, (n_sym7 // len(payload_b) + 1))[:n_sym7]
    sym_exp_a = np.repeat(sym_rep_a, SPREADING_N)
    sym_exp_b = np.repeat(sym_rep_b, SPREADING_N)
    stream_a = (sym_exp_a.real * masks7[:, 0] + 1j * sym_exp_a.imag * masks7[:, 1]).astype(np.complex64)
    stream_b = (sym_exp_b.real * masks7[:, 0] + 1j * sym_exp_b.imag * masks7[:, 1]).astype(np.complex64)
    if n_chips7 < N_SAMPLES:
        stream_a = np.concatenate([stream_a, np.zeros(N_SAMPLES - n_chips7, dtype=np.complex64)])
        stream_b = np.concatenate([stream_b, np.zeros(N_SAMPLES - n_chips7, dtype=np.complex64)])
    else:
        stream_a = stream_a[:N_SAMPLES]
        stream_b = stream_b[:N_SAMPLES]
    stream_a.tofile(os.path.join(OUTPUT_DIR, "07_nonce_reuse_transmission_A.cf32"))
    stream_b.tofile(os.path.join(OUTPUT_DIR, "07_nonce_reuse_transmission_B.cf32"))
    xor_bytes = np.bitwise_xor(stream_a.view(np.uint8), stream_b.view(np.uint8))
    xor_result = xor_bytes.view(np.complex64).copy()
    xor_result.tofile(os.path.join(OUTPUT_DIR, "07_nonce_reuse_xor_result.cf32"))
    diff_pattern = (payload_a.real - payload_b.real)[: min(len(payload_a), n_sym7)]
    stream_len = min(n_chips7, len(xor_result))
    n_full = (stream_len // SPREADING_N) * SPREADING_N
    xor_real = xor_result.real[:n_full]
    xor_by_symbol = xor_real.reshape(-1, SPREADING_N).mean(axis=1)[: len(diff_pattern)]
    corr7 = np.corrcoef(diff_pattern.flatten(), xor_by_symbol.flatten())[0, 1] if len(diff_pattern) > 1 else 0.0
    with open(os.path.join(OUTPUT_DIR, "07_nonce_reuse.json"), "w") as f:
        json.dump({"xor_correlation_vs_pattern": float(corr7)}, f, indent=2)
    if abs(corr7) > 0.1:
        print("WARNING: Nonce reuse produces detectable signal correlation. Never reuse key+nonce in production.", file=sys.stderr)

    # File 8 - Placeholder README
    readme8 = """Real noise recording instructions for gr-k-gdss IQ test files.

Sample rate: 500 kHz
Duration: minimum 10 seconds
Format: complex float32 (interleaved I,Q), same as other test files.
Connection: Antenna -> SDR Source -> File Sink. Save as 08_real_noise_reference.cf32 (or use
 08_real_noise_with_hardware_artifacts.cf32 from the project sdr-noise folder as baseline).
No transmission during recording.
Compare against Files 1 and 3 using analyse_iq_files.py.

Optional baseline with hardware artifacts (SDR recording):
  Copy from: PROJECTS_DIR/GR-K-GDSS/sdr-noise/08_real_noise_with_hardware_artifacts.cf32
  to this directory (iq_files/) as 08_real_noise_with_hardware_artifacts.cf32.
  Then analyse_iq_files.py will run the same noise tests on File 8.
"""
    with open(os.path.join(OUTPUT_DIR, "08_real_noise_placeholder_README.txt"), "w") as f:
        f.write(readme8)

    print("Generated all IQ test files in", OUTPUT_DIR)


if __name__ == "__main__":
    main()
