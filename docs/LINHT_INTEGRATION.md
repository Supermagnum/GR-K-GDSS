# LinHT ZeroMQ integration (GR-K-GDSS)

This note describes how to run keyed GDSS through a [LinHT](https://github.com/M17-Project/LinHT-hw) Rev B style baseband path that uses ZeroMQ for I/Q and side channels instead of opening both Audio Source and Audio Sink in one GNU Radio flowgraph.

## Architecture (conceptual)

```
LinHT device / daemon
        |
        |  RX IQ PUB  --------->  flowgraph ZMQ SUB -> GDSS RX chain
        |
        |  TX IQ SUB  <---------  flowgraph ZMQ PUB <- GDSS TX chain
        |
        |  PTT PUB    --------->  flowgraph ZMQ SUB -> optional `ptt` message port
        |
        v
  RF events SUB  <---------  flowgraph ZMQ PUB (sync acquired / lost, etc.)
```

ASCII overview:

```
+-------------+     PUB (IQ)      +------------------+
| LinHT       | ----------------> | GNU Radio        |
| daemon      | <---------------- | (ZMQ SUB source) |
|             |     PUB (IQ)      +------------------+
| PTT PUB ----|----------------> | (PTT -> spreader) |
| events SUB<-|----------------- | (status publish) |
+-------------+                   +------------------+
```

Exact socket addresses depend on your LinHT build; defaults used in this repository mirror common IPC paths:

| Role | Typical IPC address | Typical TCP substitute |
|------|---------------------|-------------------------|
| RX IQ (daemon publishes) | `ipc:///tmp/linht_rx` | `tcp://host:17100` |
| TX IQ (flowgraph publishes) | `ipc:///tmp/linht_tx` | `tcp://host:17101` |
| PTT strings (`ptt_on` / `ptt_off`) | `ipc:///tmp/linht_ptt` | (site-specific) |
| RF events (flowgraph publishes) | `ipc:///tmp/linht_events` | (site-specific) |

**Note:** With `pyzmq`, `inproc://` endpoints only work between sockets sharing the same `zmq.Context`. The LinHT daemon and GNU Radio each use their own context, so use **IPC or TCP** between processes.

## Security: key gate vs PTT

The Keyed GDSS spreader **never produces keyed chips without a valid session key** (`set_key` with 32-byte key and 12-byte nonce). Optional **PTT gating** adds a second requirement when the `ptt` message port is connected:

- **No key** implies **no RF chips**, regardless of PTT.
- When `ptt` is **wired**, `ptt_off` (or boolean false) **suppresses output** even if a key is armed.
- When `ptt` is **not wired**, behaviour matches older flowgraphs: gate defaults to “transmit allowed” if a key is present.

GNU Radio 4: `LinhtPttSource` emits messages with `{"ptt": <bool>}`; connect its `ptt_out` to `KgdssSpreaderCc` `ptt`. The spreader engine enforces both key and PTT state.

## Python helpers

Install the OOT module as usual; then:

- **`LinhtBridge`** (`python/linht_bridge.py`): optional holder for SUB/PUB sockets used outside GNU Radio blocks. Set **`ptt_command_endpoint`** only if your site exposes a PUSH/consumer for software PTT injection; normally the handheld publishes PTT and the flowgraph **subscribes**.
- **`LinhtPttMsgSource`**: GNU Radio 3.x `basic_block` that SUBscribes to the PTT endpoint and posts PMT symbols `ptt_on` / `ptt_off` on message port `ptt`.
- **`LinhtRfEventSink`**: publishes short UTF-8 strings from message port `events` to the daemon.

Imports: `from gnuradio import kgdss` then `kgdss.LinhtPttMsgSource(...)`, or `from gnuradio.kgdss.linht_bridge import ...` after install.

## GNU Radio 4 block

Header: `gnuradio4/include/gnuradio-4.0/kgdss/LinhtPttSource.hpp` (requires **libzmq** at build time for live ZMQ; otherwise the block logs a warning and does not receive).

Build (typical):

```bash
cd gnuradio4 && mkdir build && cd build
CMAKE_PREFIX_PATH="/opt/gnuradio4-gcc" cmake .. -DGR_K_GDSS4_BUILD_TESTS=ON
cmake --build . && ctest
```

## Example flowgraphs

Under **examples/**:

| File | Purpose |
|------|---------|
| `tx_kgdss_linht.grc` | TX-oriented companion (GNU Radio Companion); uses same KGDSS blocks as `tx_example_kgdss.grc` with ZMQ Pub Sink toward LinHT. |
| `tx_kgdss_linht.py` | Generated or companion script; documents endpoint overrides for TCP vs IPC. |
| `rx_kgdss_linht.grc` / `.py` | RX chain stub: ZMQ Sub Source into AGC and `kgdss_despreader_cc`; LDPC / superframe / Opus blocks when `gr-sleipnir` / `gr-opus` are available. |
| `loopback_kgdss_linht.grc` / `.py` | ZMQ loopback or internal noise channel for bench testing without RF hardware. |

Adjust **sample rate** (often **500 ksps**) and **UHF frequency plan** to your regulator; LinHT Rev B is **UHF only**.

## Key injection path

Align with [docs/USAGE.md](USAGE.md): **Galdralag / gr-linux-crypto** session material, **`key_injector`** or equivalent, **`set_key`** into `kgdss_spreader_cc` / `kgdss_despreader_cc`, optional **PTT** message path from LinHT.

## End-to-end keyed GDSS (matched mask)

Both `kgdss_spreader_cc` and `kgdss_despreader_cc` derive their Gaussian chip masks from the **same ChaCha20-IETF keystream** using the **`gdss_masking`** subkey (32 bytes) and a **12-byte nonce** from `gdss_nonce()` in `python/session_key_derivation.py`. `derive_session_keys()` is the single source of truth for HKDF labels (`gdss-chacha20-masking-v1`, etc.). The LinHT **loopback** example uses that derivation for TX and RX and prints a **lag searched correlation** between tapped TX symbols and despread symbols so CI or manual runs can confirm the modem path (not only ZMQ plumbing).

## Loopback test

1. Start **`loopback_kgdss_linht.grc`** (or the Python flowgraph) so TX publishes and RX subscribes on paired TCP ports (for example `127.0.0.1:17100` / `17101`) or use a single host with PUB/SUB on the same broker.
2. Confirm **sync / event** messages on `linht_events` if wired.
3. Tune **AWGN** or **channel** blocks to stress the despreader at target Es/N0.
4. After stopping the flowgraph, check the printed **correlation** line: with the correct `gdss_masking` key and nonce on both sides, the max lag-normalized correlation should be clearly above zero despite AWGN; a wrong key would not produce a stable match.

## References

- LinHT hardware: <https://github.com/M17-Project/LinHT-hw>
- Main project README: [README.md](../README.md)
