#!/usr/bin/env bash
# Run local demonstrations; each script initializes and removes its own store.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
if ! "$PYTHON" -c "import planfile"; then
    echo "Install planfile in your chosen Python environment before running examples." >&2
    exit 1
fi
for script in "$SCRIPT_DIR"/[0-9]*.py; do
    "$PYTHON" "$script"
done
echo "All examples completed; disposable stores removed."
