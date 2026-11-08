#!/usr/bin/env bash
# T06: install the offline Vosk ASR model into an existing Flow install.
#
# Run on the device after install.sh:
#   sudo bash deploy/setup-voice.sh
#
# Idempotent: an importable vosk package and an unpacked model are kept,
# and .env is edited in place (mode 600). The model runs locally, so the
# device keeps hearing you with no network at all.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FLOW_HOME="${FLOW_HOME:-/opt/flow}"
FLOW_USER="${FLOW_USER:-flow}"
MODEL_NAME="vosk-model-small-cn-0.22"
MODEL_URL=""
SKIP_APT=0
NO_TTS=0
NO_RESTART=0

usage() {
  cat <<'EOF'
Usage: sudo bash deploy/setup-voice.sh [options]

Options:
  --home PATH       install root (default: /opt/flow)
  --user NAME       service user (default: flow)
  --model NAME      Vosk model name (default: vosk-model-small-cn-0.22)
  --model-url URL   download from this URL instead of alphacephei.com
  --skip-apt        do not install unzip / espeak-ng
  --no-tts          skip espeak-ng (recognition still works)
  --no-restart      do not restart flow-backend
  -h, --help        show this help
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --home) FLOW_HOME="${2:-}"; shift 2 ;;
    --user) FLOW_USER="${2:-}"; shift 2 ;;
    --model) MODEL_NAME="${2:-}"; shift 2 ;;
    --model-url) MODEL_URL="${2:-}"; shift 2 ;;
    --skip-apt) SKIP_APT=1; shift ;;
    --no-tts) NO_TTS=1; shift ;;
    --no-restart) NO_RESTART=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "setup-voice.sh: unknown option $1" >&2; usage; exit 2 ;;
  esac
done

if [ "$(id -u)" -ne 0 ]; then
  echo "setup-voice.sh: run as root (sudo)" >&2
  exit 1
fi

VENV_PY="${FLOW_HOME}/.venv/bin/python"
ENV_FILE="${FLOW_HOME}/.env"
if [ ! -x "${VENV_PY}" ]; then
  echo "setup-voice.sh: ${VENV_PY} not found; run install.sh first" >&2
  exit 1
fi
if [ ! -f "${ENV_FILE}" ]; then
  echo "setup-voice.sh: ${ENV_FILE} not found; run install.sh first" >&2
  exit 1
fi

MODELS_DIR="${FLOW_HOME}/models"
MODEL_DIR="${MODELS_DIR}/${MODEL_NAME}"
if [ -z "${MODEL_URL}" ]; then
  MODEL_URL="https://alphacephei.com/vosk/models/${MODEL_NAME}.zip"
fi

if [ "${SKIP_APT}" -eq 0 ]; then
  need_apt=()
  command -v curl >/dev/null 2>&1 || need_apt+=(curl)
  command -v unzip >/dev/null 2>&1 || need_apt+=(unzip)
  if [ "${NO_TTS}" -eq 0 ] \
    && ! command -v espeak-ng >/dev/null 2>&1 \
    && ! command -v espeak >/dev/null 2>&1; then
    need_apt+=(espeak-ng)
  fi
  if [ "${#need_apt[@]}" -gt 0 ]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq "${need_apt[@]}"
  fi
fi

if "${VENV_PY}" -c "import vosk" >/dev/null 2>&1; then
  echo "vosk package: already installed"
else
  echo "vosk package: installing into ${FLOW_HOME}/.venv"
  "${VENV_PY}" -m pip install --no-cache-dir vosk
fi

if [ -d "${MODEL_DIR}" ] && [ -n "$(ls -A "${MODEL_DIR}" 2>/dev/null || true)" ]; then
  echo "model: already present at ${MODEL_DIR}"
else
  echo "model: downloading ${MODEL_NAME}"
  mkdir -p "${MODELS_DIR}"
  tmp="$(mktemp -d)"
  trap 'rm -rf "${tmp}"' EXIT
  if ! curl -fL --retry 3 --connect-timeout 15 -o "${tmp}/model.zip" "${MODEL_URL}"; then
    echo "setup-voice.sh: download failed; pass --model-url with a reachable mirror" >&2
    exit 1
  fi
  unzip -q "${tmp}/model.zip" -d "${MODELS_DIR}"
  rm -rf "${tmp}"
  trap - EXIT
  if [ ! -d "${MODEL_DIR}" ]; then
    echo "setup-voice.sh: ${MODEL_DIR} missing after unzip" >&2
    exit 1
  fi
fi

if grep -q '^FLOW_VOSK_MODEL=' "${ENV_FILE}"; then
  sed -i "s|^FLOW_VOSK_MODEL=.*|FLOW_VOSK_MODEL=${MODEL_DIR}|" "${ENV_FILE}"
else
  printf '\nFLOW_VOSK_MODEL=%s\n' "${MODEL_DIR}" >> "${ENV_FILE}"
fi
chown "${FLOW_USER}:${FLOW_USER}" "${ENV_FILE}"
chmod 600 "${ENV_FILE}"
chown -R "${FLOW_USER}:${FLOW_USER}" "${MODELS_DIR}"

echo "env: FLOW_VOSK_MODEL=${MODEL_DIR}"

if [ "${NO_RESTART}" -eq 1 ]; then
  echo "restart skipped; run: sudo systemctl restart flow-backend"
  exit 0
fi

systemctl restart flow-backend
for _ in $(seq 1 30); do
  if curl -fsS --max-time 1 http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

"${VENV_PY}" - <<'PY' || true
import json
import urllib.request

try:
    with urllib.request.urlopen("http://127.0.0.1:8000/healthz", timeout=5) as resp:
        data = json.load(resp)
except Exception as exc:  # noqa: BLE001 - report, never fail the setup
    print(f"healthz unavailable: {exc}")
else:
    voice = data.get("voice") or {}
    state = voice.get("state", "unknown")
    detail = str(voice.get("detail") or "").strip()
    print(f"voice: {state}{' - ' + detail if detail else ''}")
PY
