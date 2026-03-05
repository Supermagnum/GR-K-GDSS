#!/usr/bin/env python3
"""
Verify tx_example_kgdss.grc: YAML syntax, grcc generation, Python syntax,
block name uniqueness, connection integrity, and message port names.

Run from examples/: python3 verify_tx_example_kgdss.py
"""
import subprocess
import sys
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent
GRC_FILE = EXAMPLES_DIR / "tx_example_kgdss.grc"
PY_FILE = EXAMPLES_DIR / "tx_example_kgdss.py"
# GRC uses port label for message ports; key_injector output label is set_key
BLOCK_DEFS = {
    "kgdss_key_injector": {"outputs": ["key_out", "set_key"], "inputs": ["trigger", "shared_secret"]},
    "kgdss_spreader_cc": {"outputs": [], "inputs": ["set_key"]},
}

def main():
    import yaml

    failed = False

    # Step 1: YAML syntax
    try:
        with open(GRC_FILE) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print("Step 1 YAML: FAIL -", e)
        return 1
    print("Step 1 YAML: PASS")

    # Step 2b: Generate Python with grcc
    r = subprocess.run(
        ["grcc", str(GRC_FILE)],
        cwd=str(EXAMPLES_DIR),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print("Step 2b grcc: FAIL")
        if r.stderr:
            for line in r.stderr.strip().split("\n")[-20:]:
                print(" ", line)
        failed = True
    elif not PY_FILE.exists():
        print("Step 2b grcc: FAIL - tx_example_kgdss.py not produced")
        failed = True
    else:
        print("Step 2b grcc: PASS - tx_example_kgdss.py produced")

    # Step 2c: Python syntax check on generated file
    if PY_FILE.exists():
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", str(PY_FILE)],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            print("Step 2c py_compile: FAIL -", r.stderr or r.stdout)
            failed = True
        else:
            print("Step 2c py_compile: PASS")

    blocks = data.get("blocks", [])
    connections = data.get("connections", [])

    # Step 2: Block name uniqueness (instance names used in connections)
    names = [b["name"] for b in blocks]
    dupes = [n for n in names if names.count(n) > 1]
    if dupes:
        print("Step 2 Block name uniqueness: FAIL - duplicates:", dupes)
    else:
        print("Step 2 Block name uniqueness: PASS - all block names unique")
    print("  Block names:", names)
    print("  Block types (id):", [b["id"] for b in blocks])

    # Step 3: Connection integrity
    block_names = set(names)
    broken = []
    stream_ports_invalid = []
    for c in connections:
        if len(c) != 4:
            broken.append((c, "not 4-tuple"))
            continue
        src, sp, dst, dp = c
        if src not in block_names:
            broken.append((c, "source block not in flowgraph"))
        if dst not in block_names:
            broken.append((c, "destination block not in flowgraph"))
        # Stream connections use numeric ports; message connections use port names
        try:
            sp_num = int(sp)
            dp_num = int(dp)
            if sp_num < 0 or dp_num < 0:
                stream_ports_invalid.append((c, "negative port"))
        except (ValueError, TypeError):
            pass  # port is a name (message port), checked in Step 4

    if broken or stream_ports_invalid:
        print("Step 3 Connection integrity: FAIL")
        for b in broken:
            print("  Broken:", b)
        for s in stream_ports_invalid:
            print("  Invalid port:", s)
    else:
        print("Step 3 Connection integrity: PASS - all source/dest exist, stream ports non-negative")
    print("  Connections:", connections)

    # Step 4: Message port connection check
    name_to_id = {b["name"]: b["id"] for b in blocks}
    msg_issues = []
    for c in connections:
        src, sp, dst, dp = c
        try:
            int(sp)
            int(dp)
            continue  # stream connection
        except (ValueError, TypeError):
            pass  # message connection
        src_type = name_to_id.get(src)
        dst_type = name_to_id.get(dst)
        if src_type not in BLOCK_DEFS:
            msg_issues.append((c, "source block type not in message port defs"))
            continue
        if dst_type not in BLOCK_DEFS:
            msg_issues.append((c, "dest block type not in message port defs"))
            continue
        if sp not in BLOCK_DEFS[src_type]["outputs"]:
            msg_issues.append((c, f"source port '{sp}' not in {BLOCK_DEFS[src_type]['outputs']}"))
        if dp not in BLOCK_DEFS[dst_type]["inputs"]:
            # spreader has stream input 0 and message input set_key; BLOCK_DEFS only has message inputs
            if dst_type == "kgdss_spreader_cc" and dp == "set_key":
                pass  # known
            elif dp not in BLOCK_DEFS[dst_type]["inputs"]:
                msg_issues.append((c, f"dest port '{dp}' not in {BLOCK_DEFS[dst_type]['inputs']}"))

    if msg_issues:
        print("Step 4 Message port connections: FAIL")
        for m in msg_issues:
            print("  ", m)
    else:
        print("Step 4 Message port connections: PASS - set_key matches block definitions")

    if failed or dupes or broken or stream_ports_invalid or msg_issues:
        return 1
    return 0

if __name__ == "__main__":
    exit(main())
