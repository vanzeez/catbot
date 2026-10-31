#!/bin/bash
# Show which macOS permissions Catbot's desktop app (Electron) has. Prompts for nothing.
cd "$(dirname "$0")/.." || exit 1
ELECTRON=electron/node_modules/.bin/electron
[ -x "$ELECTRON" ] || { echo "run: npm --prefix electron install"; exit 1; }
"$ELECTRON" scripts/permprobe 2>/dev/null | grep -E "^(microphone|screen) "
delay=$(sysadminctl -screenLock status 2>&1 | grep -o "[0-9]* seconds\|immediate\|off" | head -1)
echo "lock delay ${delay:-unknown}  (want: immediate or 0 seconds)"
echo "desktop    macOS asks the first time Catbot touches ~/Desktop: click Allow"
