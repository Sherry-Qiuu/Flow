#!/usr/bin/env bash
# Chromium kiosk launcher used by flow-ui.service.
set -euo pipefail

URL="${FLOW_UI_URL:-http://127.0.0.1:8000}"
: "${HOME:=/home/flow}"
FLOW_HOME="${FLOW_HOME:-$(cd "$(dirname "$0")/.." && pwd)}"

# Wait for the backend so the first frame is not a connection error.
for _ in $(seq 1 60); do
  if curl -fsS --max-time 1 "${URL}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# X11 quality-of-life: no blanking, no cursor sitting on the screen.
xset -dpms 2>/dev/null || true
xset s off 2>/dev/null || true
xset s noblank 2>/dev/null || true
if command -v unclutter >/dev/null 2>&1; then
  unclutter -idle 0.5 -root >/dev/null 2>&1 &
fi
if command -v openbox >/dev/null 2>&1; then
  openbox >/dev/null 2>&1 &
fi
if command -v xbindkeys >/dev/null 2>&1 \
  && [ -f "${FLOW_HOME}/config/xbindkeysrc" ]; then
  xbindkeys -f "${FLOW_HOME}/config/xbindkeysrc" >/dev/null 2>&1 &
fi

CHROMIUM="${CHROMIUM_BIN:-}"
if [ -z "${CHROMIUM}" ]; then
  if command -v chromium >/dev/null 2>&1; then
    CHROMIUM="chromium"
  elif command -v chromium-browser >/dev/null 2>&1; then
    CHROMIUM="chromium-browser"
  else
    echo "flow-kiosk: chromium is not installed" >&2
    exit 1
  fi
fi

PROFILE="${HOME}/.config/flow-chromium"
mkdir -p "${PROFILE}"

exec "${CHROMIUM}" \
  --kiosk \
  --start-fullscreen \
  --window-position=0,0 \
  --window-size=720,720 \
  --force-device-scale-factor=1 \
  --no-first-run \
  --no-default-browser-check \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-translate \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --password-store=basic \
  --check-for-update-interval=31536000 \
  --disable-background-timer-throttling \
  --disable-renderer-backgrounding \
  --disable-backgrounding-occluded-windows \
  --user-data-dir="${PROFILE}" \
  "${URL}"
