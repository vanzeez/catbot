#!/bin/bash
# Start Catbot as its own macOS app. macOS charges microphone and screen permissions to the app
# that launched a process; started from a terminal, Catbot inherits that terminal's permissions
# (a terminal without mic access gives "Permission denied"). Launched with `open`, Electron owns
# its permissions and macOS asks once: click Allow.
#
#   ./scripts/start_catbot.sh            full view
#   CATBOT_VIEW=billu ./scripts/start_catbot.sh   Billu mode
# Logs: data/catbot.log
set -euo pipefail
cd "$(dirname "$0")/.."
APP="$PWD/electron/node_modules/electron/dist/Electron.app"
[ -d "$APP" ] || npm --prefix electron install
pkill -f "electron/dist/Electron.app/Contents/MacOS/Electron" 2>/dev/null || true
pkill -f "catbot --serve" 2>/dev/null || true
sleep 1
mkdir -p data
open -n -a "$APP" --env "PATH=$PATH" --env "CATBOT_VIEW=${CATBOT_VIEW:-}" \
  --stdout "$PWD/data/catbot.log" --stderr "$PWD/data/catbot.log" --args "$PWD/electron"
echo "Catbot is starting (about 10 s). Logs: data/catbot.log"
