#!/usr/bin/env bash
# T01 + T06: turn an installed device into a standalone one.
#
#   sudo bash deploy/setup-standalone.sh --display hdmi720
#
# One command that does what the manual bring-up used to need: write the
# boot display mode, install offline speech recognition, make sure every
# unit starts at boot, restart the stack and print a single summary. After
# a reboot the device runs on its own - no laptop, no shell session.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FLOW_HOME="${FLOW_HOME:-/opt/flow}"
FLOW_USER="${FLOW_USER:-flow}"
DISPLAY_MODE="hdmi720"
WITH_VOICE=1
SKIP_APT=0
NO_RESTART=0

usage() {
  cat <<'EOF'
Usage: sudo bash deploy/setup-standalone.sh [options]

Options:
  --display hdmi720|hdmi1024x600|hdmi1280x800|dsi|none
                               boot display mode (default: hdmi720)
  --home PATH                  install root (default: /opt/flow)
  --user NAME                  service user (default: flow)
  --no-voice                   skip the offline ASR step
  --skip-apt                   never call apt-get
  --no-restart                 prepare only, leave services untouched
  -h, --help                   show this help
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --display) DISPLAY_MODE="${2:-}"; shift 2 ;;
    --home) FLOW_HOME="${2:-}"; shift 2 ;;
    --user) FLOW_USER="${2:-}"; shift 2 ;;
    --no-voice) WITH_VOICE=0; shift ;;
    --skip-apt) SKIP_APT=1; shift ;;
    --no-restart) NO_RESTART=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "setup-standalone.sh: unknown option $1" >&2; usage; exit 2 ;;
  esac
done

case "${DISPLAY_MODE}" in
  hdmi720|hdmi1024x600|hdmi1280x800|dsi|none) ;;
  *) echo "--display must be hdmi720, hdmi1024x600, hdmi1280x800, dsi or none" >&2; exit 2 ;;
esac

if [ "$(id -u)" -ne 0 ]; then
  echo "setup-standalone.sh: run as root (sudo)" >&2
  exit 1
fi
if [ ! -f "${FLOW_HOME}/config.yaml" ]; then
  echo "setup-standalone.sh: ${FLOW_HOME}/config.yaml not found" >&2
  echo "run install.sh first" >&2
  exit 1
fi

DISPLAY_CHANGED=0
if [ "${DISPLAY_MODE}" != "none" ]; then
  if [ -x /usr/local/bin/flow-display ]; then
    /usr/local/bin/flow-display "${DISPLAY_MODE}"
  else
    bash "${SCRIPT_DIR}/configure-display.sh" "${DISPLAY_MODE}"
  fi
  DISPLAY_CHANGED=1
fi

if [ "${WITH_VOICE}" -eq 1 ]; then
  voice_args=(--home "${FLOW_HOME}" --user "${FLOW_USER}" --no-restart)
  [ "${SKIP_APT}" -eq 1 ] && voice_args+=(--skip-apt)
  bash "${SCRIPT_DIR}/setup-voice.sh" "${voice_args[@]}"
fi

for unit in flow-hal flow-backend flow-ui; do
  systemctl enable "${unit}.service" >/dev/null 2>&1 || true
done

if [ "${NO_RESTART}" -eq 0 ]; then
  systemctl restart flow-hal.service
  systemctl restart flow-backend.service flow-ui.service
  for _ in $(seq 1 40); do
    if curl -fsS --max-time 1 http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

echo
echo "Standalone checklist"
for unit in flow-hal flow-backend flow-ui; do
  enabled="$(systemctl is-enabled "${unit}.service" 2>/dev/null || true)"
  active="$(systemctl is-active "${unit}.service" 2>/dev/null || true)"
  printf '  %-14s boot:%-10s now:%s\n' "${unit}" "${enabled:-unknown}" "${active:-unknown}"
done
printf '  %-14s %s\n' "display" "${DISPLAY_MODE}"
if [ "${WITH_VOICE}" -eq 1 ]; then
  printf '  %-14s %s\n' "asr" "${FLOW_HOME}/models (offline vosk)"
fi

if [ "${DISPLAY_CHANGED}" -eq 1 ]; then
  echo
  echo "Reboot to apply the display mode: sudo reboot"
fi
