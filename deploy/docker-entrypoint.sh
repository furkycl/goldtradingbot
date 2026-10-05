#!/bin/sh
# Bind-mounted ./state is usually created as root on the host; fix ownership,
# then drop privileges. The bot itself never runs as root.
set -e
mkdir -p /app/state
chown -R goldbot:goldbot /app/state 2>/dev/null || true
exec setpriv --reuid=goldbot --regid=goldbot --init-groups python -m goldbot "$@"
