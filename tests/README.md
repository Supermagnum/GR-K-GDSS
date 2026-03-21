![Open Invention Network member](../docs/oin-member-horiz.jpg)

# gr-k-gdss unit tests

Tests load `gnuradio.kgdss` from the system Python path (e.g. after `make install`). **You must install the module from your build directory before running tests**, or they will use an older installed version:

```bash
cd build
make -j4
sudo make install
cd ..
export PYTHONPATH="/usr/local/lib/python3.12/dist-packages:/usr/lib/python3.12/dist-packages:$PYTHONPATH"
pytest tests/ -v
```

Or use the helper script (same PYTHONPATH logic):

```bash
./tests/run_tests.sh
```

To confirm which module is used (run with the same env as pytest, e.g. venv):

```bash
source ~/gr-test-env/bin/activate   # or your venv
python3 -c "import gnuradio.kgdss.kgdss_python as m; print(m.__file__)"
```

That path should be under your install prefix (e.g. `/usr/local/...` after `sudo make install` from `build`). If you see a path under `/usr/` but you installed from `build` to `/usr/local`, set `PYTHONPATH` so the install prefix comes first, or install to the same prefix your Python uses.

**Testing without sudo (local install):** From repo root, install into a local prefix then point Python at it:

```bash
cd build
cmake -DCMAKE_INSTALL_PREFIX=$PWD/install ..
make -j4
make install
cd ..
export PYTHONPATH="build/install/lib/python3.12/dist-packages:$PYTHONPATH"
pytest tests/ -v
```

(Use `site-packages` instead of `dist-packages` if your system uses that.)

Or with unittest:

```bash
python -m unittest discover -s tests -v
```

- **T1** (test_t1_spreader_despreader.py): Keyed spreader/despreader C++ blocks via Python bindings. Skipped if bindings are not available.
- **T2** (test_t2_sync_burst.py): Sync burst Python helpers (PN sequence, timing schedule, Gaussian envelope).
- **T3** (test_t3_key_derivation.py): Key derivation and nonce construction. Keyring round-trip is skipped if the Linux keyring is not available.
- **Cross-layer** (test_cross_layer.py): Full stack round-trip using derived keys and keyed blocks.

**Keyring test skipped:** If the keyring round-trip test is skipped, the skip message now shows the import error (e.g. `No module named 'gr_linux_crypto'`). Ensure gr-linux-crypto is installed for the same Python you use for pytest, and that its install path is on `PYTHONPATH` before you run tests. For example, if gr-linux-crypto is in `/usr/local/lib/python3.12/dist-packages`, that path must be in `PYTHONPATH` (as in the examples above).

Install pytest if needed: `pip install pytest`
