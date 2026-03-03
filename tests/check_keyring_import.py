#!/usr/bin/env python3
"""
Print why keyring import fails and suggest PYTHONPATH.
Run with the same Python/venv you use for pytest.
"""
import sys

def main():
    print("Python:", sys.executable)
    print("sys.path:")
    for p in sys.path:
        print("  ", p)
    print()

    # Try each known import path (gr_linux_crypto has module keyring_helper, class KeyringHelper)
    tried = [
        "gr_linux_crypto.keyring_helper",
        "gr_linux_crypto.python.keyring_helper",
        "gr_linux_crypto",
        "gnuradio.linux_crypto.python.keyring_helper",
        "gnuradio.linux_crypto.keyring_helper",
        "gnuradio.linux_crypto",
        "gnuradio.linux_crypto_python",
        "linux_crypto_python",
        "keyring_helper",
    ]
    for path in tried:
        try:
            import importlib
            mod = importlib.import_module(path)
            kh = getattr(mod, "KeyringHelper", None)
            if kh is not None:
                print("OK: {} (KeyringHelper found)".format(path))
                print("    Module file:", getattr(mod, "__file__", "?"))
                # Show package root for PYTHONPATH hint
                root = path.split(".")[0]
                try:
                    root_mod = importlib.import_module(root)
                    print("    Package root '{}' at: {}".format(root, getattr(root_mod, "__file__", "?")))
                except Exception:
                    pass
                return 0
            print("    Import OK but KeyringHelper not in module")
        except ImportError as e:
            print("FAIL: {} -> {}".format(path, e))
        except Exception as e:
            print("FAIL: {} -> {}".format(path, e))

    # If gnuradio.linux_crypto loaded, show what it has (for debugging)
    try:
        lc = importlib.import_module("gnuradio.linux_crypto")
        attrs = [x for x in dir(lc) if not x.startswith("_")]
        print("gnuradio.linux_crypto attributes (no KeyringHelper):", attrs[:20])
        if len(attrs) > 20:
            print("  ... and", len(attrs) - 20, "more")
    except Exception:
        pass

    print()
    print("KeyringHelper not found. To fix:")
    print("  1. Use gr-linux-crypto source tree (KeyringHelper is in python/keyring_helper.py):")
    print('     export GR_LINUX_CRYPTO_DIR="/path/to/gr-linux-crypto"')
    print("     pytest tests/ -v")
    print("  2. Or install gr-linux-crypto so KeyringHelper is on PYTHONPATH.")
    return 1

if __name__ == "__main__":
    sys.exit(main())
