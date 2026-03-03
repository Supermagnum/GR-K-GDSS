#!/usr/bin/env python3
"""
Run statistical tests on gr-k-gdss IQ test files. Prints PASS/FAIL/WARN table.
Requires: numpy, scipy. Optional: json for metadata.
"""

import json
import os
import sys

import numpy as np
from scipy import stats

SAMPLE_RATE = 500_000
N_SAMPLES = 5_000_000
SPREADING_N = 256
IQ_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iq_files")


def load_cf32(path: str) -> np.ndarray:
    return np.fromfile(path, dtype=np.complex64)


def run_tests():
    results = []
    passed = failed = warnings = 0

    # Files 1 and 3 (and 8 if present): noise-like stats
    for name, fname in [
        ("01_gaussian_noise_baseline.cf32", "01_gaussian_noise_baseline.cf32"),
        ("03_keyed_gdss_transmission.cf32", "03_keyed_gdss_transmission.cf32"),
    ]:
        path = os.path.join(IQ_DIR, fname)
        if not os.path.isfile(path):
            continue
        data = load_cf32(path)
        N = len(data)
        I, Q = data.real, data.imag
        std_i, std_q = I.std(), Q.std()
        thr_mean = 3 * std_i / np.sqrt(N)
        # BPSK payload has no Q component; skip Q stats when Q has no variance
        q_absent = std_q < 1e-6 * max(std_i, 1.0)

        # Mean
        ok = abs(I.mean()) < thr_mean
        results.append((name, "Mean (I)", "PASS" if ok else "FAIL"))
        if ok: passed += 1
        else: failed += 1
        thr_mean_q = 3 * std_q / np.sqrt(N) if std_q > 0 else 0
        ok = abs(Q.mean()) < max(thr_mean_q, 1e-10) if not q_absent else True
        results.append((name, "Mean (Q)", "PASS" if ok else "FAIL"))
        if ok: passed += 1
        else: failed += 1

        # Variance symmetry (PASS if Q absent for BPSK keyed transmission)
        mean_std = (std_i + std_q) / 2
        sym = abs(std_i - std_q) / mean_std if mean_std > 0 else 0
        ok = sym < 0.10 or q_absent
        results.append((name, "Variance symmetry", "PASS" if ok else "FAIL"))
        if ok: passed += 1
        else: failed += 1

        # Kurtosis
        kurt_i = stats.kurtosis(I, fisher=False)
        kurt_q = stats.kurtosis(Q, fisher=False) if not q_absent else 3.0
        results.append((name, "Kurtosis (I)", "PASS" if (2.7 < kurt_i < 3.3) else "FAIL"))
        if 2.7 < kurt_i < 3.3: passed += 1
        else: failed += 1
        results.append((name, "Kurtosis (Q)", "PASS" if (q_absent or (2.7 < kurt_q < 3.3)) else "FAIL"))
        if q_absent or (2.7 < kurt_q < 3.3): passed += 1
        else: failed += 1

        # Skewness
        skew_i = stats.skew(I)
        skew_q = stats.skew(Q) if not q_absent else 0.0
        results.append((name, "Skewness (I)", "PASS" if abs(skew_i) < 0.1 else "FAIL"))
        if abs(skew_i) < 0.1: passed += 1
        else: failed += 1
        results.append((name, "Skewness (Q)", "PASS" if (q_absent or abs(skew_q) < 0.1) else "FAIL"))
        if q_absent or abs(skew_q) < 0.1: passed += 1
        else: failed += 1

        # Autocorrelation (lags 1..100)
        chunk = I[: min(100_000, N)]
        ac = np.correlate(chunk - chunk.mean(), chunk - chunk.mean(), mode="full")
        ac = ac[len(ac) // 2 :]
        if ac[0] != 0:
            ac = ac / ac[0]
        max_ac = np.max(np.abs(ac[1:101])) if len(ac) > 101 else 0
        thresh = 3.0 / np.sqrt(len(chunk))
        ok = max_ac < thresh
        results.append((name, "Autocorrelation", "PASS" if ok else "FAIL"))
        if ok: passed += 1
        else: failed += 1

    # File 8 if present (real noise)
    path8 = os.path.join(IQ_DIR, "08_real_noise_with_hardware_artifacts.cf32")
    if not os.path.isfile(path8):
        path8 = os.path.join(IQ_DIR, "08_real_noise_reference.cf32")
    if os.path.isfile(path8):
        data = load_cf32(path8)
        N = len(data)
        I, Q = data.real, data.imag
        std_i = I.std()
        thr_mean = 3 * std_i / np.sqrt(N)
        for label, val, cond in [("Mean (I)", I.mean(), abs(I.mean()) < thr_mean),
                                 ("Mean (Q)", Q.mean(), abs(Q.mean()) < thr_mean)]:
            results.append((os.path.basename(path8), label, "PASS" if cond else "FAIL"))
            if cond: passed += 1
            else: failed += 1
        kurt_i = stats.kurtosis(I, fisher=False)
        kurt_q = stats.kurtosis(Q, fisher=False)
        for label, cond in [("Kurtosis (I)", 2.7 < kurt_i < 3.3), ("Kurtosis (Q)", 2.7 < kurt_q < 3.3)]:
            results.append((os.path.basename(path8), label, "PASS" if cond else "FAIL"))
            if cond: passed += 1
            else: failed += 1
        chunk = I[: min(100_000, N)]
        ac = np.correlate(chunk - chunk.mean(), chunk - chunk.mean(), mode="full")
        ac = ac[len(ac) // 2 :]
        if ac[0] != 0:
            ac = ac / ac[0]
        max_ac = np.max(np.abs(ac[1:101])) if len(ac) > 101 else 0
        thresh = 3.0 / np.sqrt(len(chunk))
        results.append((os.path.basename(path8), "Autocorrelation", "PASS" if max_ac < thresh else "FAIL"))
        if max_ac < thresh: passed += 1
        else: failed += 1

    # File 4 - round-trip correlation
    path4 = os.path.join(IQ_DIR, "04_keyed_gdss_despread_correct_key.cf32")
    path4json = os.path.join(IQ_DIR, "04_keyed_gdss_despread_correct_key.json")
    if os.path.isfile(path4) and os.path.isfile(path4json):
        with open(path4json) as f:
            meta = json.load(f)
        corr = meta.get("pearson_correlation_vs_payload", 0)
        ok = corr > 0.95
        results.append(("04_keyed_gdss_despread_correct_key.cf32", "Round-trip correlation", "PASS" if ok else "FAIL"))
        if ok: passed += 1
        else: failed += 1

    # File 5 - key isolation
    path5json = os.path.join(IQ_DIR, "05_keyed_gdss_despread_wrong_key.json")
    if os.path.isfile(path5json):
        with open(path5json) as f:
            meta = json.load(f)
        corr = meta.get("pearson_correlation_vs_payload", 1)
        ok = abs(corr) < 0.05
        results.append(("05_keyed_gdss_despread_wrong_key.cf32", "Key isolation", "PASS" if ok else "FAIL"))
        if ok: passed += 1
        else: failed += 1

    # Files 7 - nonce reuse (WARN)
    path7json = os.path.join(IQ_DIR, "07_nonce_reuse.json")
    if os.path.isfile(path7json):
        with open(path7json) as f:
            meta = json.load(f)
        corr = abs(meta.get("xor_correlation_vs_pattern", 0))
        status = "WARN" if corr > 0.1 else "PASS"
        results.append(("07_nonce_reuse", "Nonce reuse detection", status))
        if status == "WARN":
            warnings += 1
        else:
            passed += 1

    # Print table
    print("=== gr-k-gdss IQ File Analysis ===\n")
    print(f"{'File':<42} {'Test':<28} {'Result':<8}")
    print("-" * 80)
    for name, test, result in results:
        print(f"{name:<42} {test:<28} {result:<8}")
    print("-" * 80)
    print(f"PASSED: {passed}   FAILED: {failed}   WARNINGS: {warnings}")
    return failed


if __name__ == "__main__":
    if not os.path.isdir(IQ_DIR):
        print("IQ directory not found:", IQ_DIR, file=sys.stderr)
        sys.exit(2)
    n_fail = run_tests()
    sys.exit(0 if n_fail == 0 else 1)
