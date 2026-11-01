#!/bin/bash
# Show which macOS permissions Catbot's desktop app (Electron) has. Prompts for nothing.
cd "$(dirname "$0")/.." || exit 1
ELECTRON=electron/node_modules/.bin/electron
[ -x "$ELECTRON" ] || { echo "run: npm --prefix electron install"; exit 1; }
# Launch through `open` (like scripts/start_catbot.sh) so macOS reports Catbot's own permissions,
# not those of the terminal running this script.
APP="$PWD/electron/node_modules/electron/dist/Electron.app"
OUT="$(mktemp)"
open -W -n -a "$APP" --stdout "$OUT" --stderr /dev/null --args "$PWD/scripts/permprobe"
grep -E "^(microphone|screen) " "$OUT"; rm -f "$OUT"
delay=$(sysadminctl -screenLock status 2>&1 | grep -o "[0-9]* seconds\|immediate\|off" | head -1)
echo "lock delay ${delay:-unknown}  (want: immediate or 0 seconds)"
echo "desktop    macOS asks the first time Catbot touches ~/Desktop: click Allow"
