#!/bin/bash
# Run GR-K-GDSS tests with PYTHONPATH so the venv can see system-installed
# gnuradio, gnuradio.kgdss, and gr-linux-crypto. Use this when pytest is
# run from a virtualenv that does not use --system-site-packages.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Common locations for system Python packages (GNU Radio, gr-linux-crypto, gr-k-gdss)
for d in /usr/local/lib/python3.12/dist-packages \
         /usr/local/lib/python3.12/site-packages \
         /usr/lib/python3.12/dist-packages \
         /usr/lib/python3.12/site-packages; do
    if [ -d "$d" ]; then
    export PYTHONPATH="${d}:${PYTHONPATH:-}"
    fi
done

cd "$ROOT_DIR"
exec python -m pytest tests/ -v "$@"
