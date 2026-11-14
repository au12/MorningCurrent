#!/bin/sh
# Run as PUID:PGID (default 1000:1000; Unraid uses 99:100) and make sure the data folder is theirs.
set -e
DATA="${MC_DATA:-/data}"
mkdir -p "$DATA"
if [ "$(id -u)" = "0" ]; then
  PUID="${PUID:-1000}"
  PGID="${PGID:-1000}"
  if [ "$PUID" = "0" ]; then
    exec "$@"
  fi
  if [ "$(stat -c %u:%g "$DATA")" != "$PUID:$PGID" ]; then
    echo "[entrypoint] giving $DATA to $PUID:$PGID"
    chown -R "$PUID:$PGID" "$DATA" || echo "[entrypoint] could not change ownership of $DATA; continuing"
  fi
  export HOME="$DATA/.home"
  mkdir -p "$HOME" && chown "$PUID:$PGID" "$HOME"
  exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups -- "$@"
fi
exec "$@"
