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

# Window size follows the panel instead of a hardcoded 720x720: on a
# 1280x800 10.1" screen a 720 window would leave the canvas off-centre on
# the first frame. ui.size in config.yaml is the CSS canvas (720x720), so
# it is not a usable fallback here; FLOW_WINDOW_SIZE="1280,800" overrides.
WINDOW_SIZE="${FLOW_WINDOW_SIZE:-}"
if [ -z "${WINDOW_SIZE}" ] && command -v xrandr >/dev/null 2>&1; then
  WINDOW_SIZE="$(xrandr --current 2>/dev/null \
    | awk '/ connected/ { for (i = 1; i <= NF; i++) if ($i ~ /^[0-9]+x[0-9]+\+/) { print $i; exit } }' \
    | cut -d+ -f1)"
fi
WINDOW_SIZE="${WINDOW_SIZE:-720x720}"
WINDOW_SIZE="${WINDOW_SIZE/x/,}"

exec "${CHROMIUM}" \
  --kiosk \
  --start-fullscreen \
  --window-position=0,0 \
  --window-size="${WINDOW_SIZE}" \
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
