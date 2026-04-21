#!/usr/bin/env bash
# One-shot installer for kestrel-mcp on Linux/macOS.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$HOME/.kestrel/venv}"

echo "==> kestrel-mcp installer"
echo "    Repo:  $REPO_ROOT"
echo "    Venv:  $VENV_DIR"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found on PATH; install Python 3.10+ first." >&2
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "==> Creating venv"
    python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

echo "==> Upgrading pip"
python -m pip install --upgrade pip wheel setuptools

echo "==> Installing kestrel-mcp (editable + dev extras)"
python -m pip install -e "${REPO_ROOT}[dev]"

echo "==> Running doctor"
python -m kestrel_mcp doctor || true

echo
read -r -p "Register with Cursor now? [y/N] " ans
if [[ "$ans" =~ ^[Yy] ]]; then
    python "$REPO_ROOT/scripts/register_cursor.py"
fi

echo
echo "DONE. Activate the venv with:"
echo "    source $VENV_DIR/bin/activate"
