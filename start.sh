#!/usr/bin/env bash
# HumanWrite AI v1 - macOS/Linux launcher
set -e
cd "$(dirname "$0")"

echo "========================================================"
echo "  HumanWrite AI v1"
echo "  Make Every Word Sound Naturally Yours."
echo "========================================================"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 was not found. Install Python 3.10-3.13 first."
  exit 1
fi
python3 --version

if [ ! -x "venv/bin/python" ]; then
  echo
  echo " [1/3] First run: creating a private Python environment (one-time)..."
  python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate

if ! python -c "import flask, docx, reportlab, pypdf, requests" >/dev/null 2>&1; then
  echo
  echo " [2/3] Installing required packages (one-time, needs internet)..."
  python -m pip install --upgrade pip >/dev/null 2>&1 || true
  pip install -r requirements.txt
else
  echo " [2/3] Packages already installed - skipping."
fi

echo
echo " [3/3] Starting HumanWrite AI at http://127.0.0.1:4322"
echo " Keep this terminal open while you use the app (Ctrl+C to stop)."
(python -c "import webbrowser; webbrowser.open('http://127.0.0.1:4322')" &)
python app.py
