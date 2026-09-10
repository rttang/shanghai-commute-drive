#!/bin/sh
# Rosetta architecture preferences may survive an ARM Node child. Select the
# universal Chrome slice explicitly for this isolated acceptance browser only.
CHROME_BIN='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
if [ "$(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ]; then
  exec /usr/bin/arch -arm64 "$CHROME_BIN" "$@"
fi
exec "$CHROME_BIN" "$@"
