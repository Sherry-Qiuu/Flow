#!/usr/bin/env bash
# T01: repeatable Raspberry Pi OS Lite install for Flow.
#
# Run from the repository root on the Pi:
#   sudo bash install.sh --display hdmi720
#
# This script writes /opt/flow, a Python venv, systemd units, journald
# retention, the kiosk launcher and the flow-diag command. It never
# copies .env from the source tree and never prints secrets.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="${SCRIPT_DIR}"

FLOW_HOME="${FLOW_HOME:-/opt/flow}"
FLOW_USER="${FLOW_USER:-flow}"
DISPLAY_MODE="none"
SKIP_APT=0
SKIP_SYSTEMD=0
WITH_REAL=1
WITH_OPENCV=0
KEEP_DESKTOP=0
START_SERVICES=0

usage() {
  cat <<'EOF'
Usage: sudo bash install.sh [options]

Options:
  --display hdmi720|dsi|none   boot display mode (default: none)
  --home PATH                  install root (default: /opt/flow)
  --user NAME                  service user (default: flow)
  --no-real                    skip Raspberry Pi hardware extras
  --with-opencv                install OpenCV for USB cameras
  --skip-apt                   skip apt-get install
  --skip-systemd               do not enable units (staging/testing)
  --keep-desktop               keep graphical.target (default: multi-user)
  --start                      start services after enabling
  -h, --help                   show this help
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --display)
      DISPLAY_MODE="${2:-}"
      shift 2
      ;;
    --home)
      FLOW_HOME="${2:-}"
      shift 2
      ;;
    --user)
      FLOW_USER="${2:-}"
      shift 2
      ;;
    --no-real) WITH_REAL=0; shift ;;
    --with-opencv) WITH_OPENCV=1; shift ;;
    --skip-apt) SKIP_APT=1; shift ;;
    --skip-systemd) SKIP_SYSTEMD=1; shift ;;
    --keep-desktop) KEEP_DESKTOP=1; shift ;;
    --start) START_SERVICES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

case "${DISPLAY_MODE}" in
  hdmi720|dsi|none) ;;
  *) echo "--display must be hdmi720, dsi or none" >&2; exit 2 ;;
esac

if [ "$(id -u)" -ne 0 ]; then
  echo "install.sh: run as root (sudo)" >&2
  exit 1
fi
if [ ! -f "${SOURCE_DIR}/pyproject.toml" ]; then
  echo "install.sh: pyproject.toml not found in ${SOURCE_DIR}" >&2
  exit 1
fi
if [ "${FLOW_ALLOW_NON_PI:-0}" != "1" ]; then
  MODEL="$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || true)"
  if ! echo "${MODEL}" | grep -qi "raspberry pi"; then
    echo "install.sh: this does not look like a Raspberry Pi."
    echo "For staging only, set FLOW_ALLOW_NON_PI=1."
    exit 1
  fi
fi

APT_PACKAGES=(
  python3-venv python3-pip python3-dev
  chromium fonts-noto-cjk locales
  chrony fake-hwclock rsync curl jq sqlite3 ca-certificates git
  xserver-xorg xserver-xorg-legacy xinit x11-xserver-utils xauth openbox unclutter xbindkeys
  alsa-utils v4l-utils i2c-tools gpiod
  libportaudio2 portaudio19-dev libasound2-dev
)

if [ "${SKIP_APT}" -eq 0 ]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends "${APT_PACKAGES[@]}"
  # These packages are Pi-specific and optional on staging images.
  apt-get install -y --no-install-recommends \
    python3-picamera2 python3-gpiozero python3-lgpio python3-smbus \
    rpicam-apps \
    2>/dev/null || true
fi

if ! getent group "${FLOW_USER}" >/dev/null 2>&1; then
  groupadd "${FLOW_USER}"
fi
if ! id -u "${FLOW_USER}" >/dev/null 2>&1; then
  useradd --create-home --gid "${FLOW_USER}" --shell /bin/bash "${FLOW_USER}"
fi
for group in audio video gpio i2c spi render plugdev systemd-journal; do
  if getent group "${group}" >/dev/null 2>&1; then
    usermod -aG "${group}" "${FLOW_USER}" || true
  fi
done

if [ "${SOURCE_DIR}" != "${FLOW_HOME}" ]; then
  install -d -m 0755 "${FLOW_HOME}"
  rsync -a --delete \
    --exclude='.git' \
    --exclude='.env' \
    --exclude='.venv' \
    --exclude='data' \
    --exclude='config.yaml' \
    --exclude='version.json' \
    --exclude='.test_tmp' \
    --exclude='.pytest_tmp' \
    --exclude='.pip_tmp' \
    --exclude='.pytest_cache' \
    --exclude='pytest-cache-files-*' \
    --exclude='__pycache__' \
    "${SOURCE_DIR}/" "${FLOW_HOME}/"
fi

install -d -m 0755 "${FLOW_HOME}/bin" "${FLOW_HOME}/ui"
install -d -m 0750 -o "${FLOW_USER}" -g "${FLOW_USER}" \
  "${FLOW_HOME}/data" \
  "${FLOW_HOME}/data/inbox" \
  "${FLOW_HOME}/data/backup" \
  "${FLOW_HOME}/data/diag"

if [ ! -f "${FLOW_HOME}/config.yaml" ]; then
  cp "${SOURCE_DIR}/config.yaml" "${FLOW_HOME}/config.yaml"
fi
if [ ! -f "${FLOW_HOME}/.env" ]; then
  cp "${SOURCE_DIR}/.env.example" "${FLOW_HOME}/.env"
  chmod 600 "${FLOW_HOME}/.env"
fi

install -m 0755 "${SOURCE_DIR}/deploy/flow-kiosk.sh" \
  "${FLOW_HOME}/bin/flow-kiosk"
install -d -m 0755 "${FLOW_HOME}/config"
install -m 0644 "${SOURCE_DIR}/deploy/xbindkeysrc" \
  "${FLOW_HOME}/config/xbindkeysrc"
install -m 0755 "${SOURCE_DIR}/deploy/configure-display.sh" \
  /usr/local/bin/flow-display
sed "s|@FLOW_HOME@|${FLOW_HOME}|g" \
  "${SOURCE_DIR}/deploy/flow-diag" > /usr/local/bin/flow-diag
chmod 0755 /usr/local/bin/flow-diag

if [ ! -x "${FLOW_HOME}/.venv/bin/python" ]; then
  python3 -m venv --system-site-packages "${FLOW_HOME}/.venv"
fi
VENV_PY="${FLOW_HOME}/.venv/bin/python"
export PIP_NO_CACHE_DIR=1
"${VENV_PY}" -m pip install --upgrade pip setuptools wheel
"${VENV_PY}" -m pip install --no-build-isolation "${FLOW_HOME}"
if [ "${WITH_REAL}" -eq 1 ]; then
  "${VENV_PY}" -m pip install --no-build-isolation "${FLOW_HOME}[pi]"
fi
if [ "${WITH_OPENCV}" -eq 1 ]; then
  "${VENV_PY}" -m pip install --no-cache-dir opencv-python
fi

COMMIT="unknown"
if command -v git >/dev/null 2>&1; then
  COMMIT="$(git -C "${SOURCE_DIR}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
fi
cat > "${FLOW_HOME}/version.json" <<EOF
{
  "version": "0.1.0",
  "commit": "${COMMIT}",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

if [ ! -f /etc/systemd/journald.conf.d/flow.conf ]; then
  install -d -m 0755 /etc/systemd/journald.conf.d
  install -m 0644 "${SOURCE_DIR}/deploy/systemd/journald-flow.conf" \
    /etc/systemd/journald.conf.d/flow.conf
fi

bash_locale_gen() {
  if [ -f /etc/locale.gen ]; then
    sed -i 's/^# *zh_CN.UTF-8 UTF-8/zh_CN.UTF-8 UTF-8/' /etc/locale.gen || true
    locale-gen || true
    update-locale LANG=zh_CN.UTF-8 2>/dev/null || true
  fi
}
bash_locale_gen
timedatectl set-timezone Asia/Shanghai 2>/dev/null || true
systemctl enable --now chrony 2>/dev/null || true
if [ "${KEEP_BLUETOOTH:-0}" != "1" ]; then
  systemctl disable --now bluetooth 2>/dev/null || true
fi

# Allow the service user to start Xorg from the systemd login session.
if [ -f /etc/X11/Xwrapper.config ]; then
  sed -i 's/^allowed_users=.*/allowed_users=anybody/' /etc/X11/Xwrapper.config || true
  grep -q '^needs_root_rights=' /etc/X11/Xwrapper.config || \
    echo 'needs_root_rights=yes' >> /etc/X11/Xwrapper.config
fi

if [ "${DISPLAY_MODE}" != "none" ]; then
  /usr/local/bin/flow-display "${DISPLAY_MODE}"
fi

if [ "${SKIP_SYSTEMD}" -eq 0 ]; then
  for unit in flow-hal flow-backend flow-ui; do
    sed \
      -e "s|@FLOW_HOME@|${FLOW_HOME}|g" \
      -e "s|@FLOW_USER@|${FLOW_USER}|g" \
      "${SOURCE_DIR}/deploy/systemd/${unit}.service" \
      > "/etc/systemd/system/${unit}.service"
    chmod 0644 "/etc/systemd/system/${unit}.service"
  done
  systemctl daemon-reload
  systemctl enable flow-hal.service flow-backend.service flow-ui.service
  systemctl restart systemd-journald 2>/dev/null || true
  if [ "${KEEP_DESKTOP}" -eq 0 ]; then
    systemctl set-default multi-user.target 2>/dev/null || true
  fi
  if [ "${START_SERVICES}" -eq 1 ]; then
    systemctl start flow-hal.service flow-backend.service flow-ui.service
  fi
fi

chown -R "${FLOW_USER}:${FLOW_USER}" "${FLOW_HOME}"
chmod 600 "${FLOW_HOME}/.env"
chmod 0755 "${FLOW_HOME}/bin/flow-kiosk"

cat <<EOF

Flow installed at ${FLOW_HOME}
  user:        ${FLOW_USER}
  backend:     http://127.0.0.1:8000
  kiosk:       ${FLOW_HOME}/bin/flow-kiosk
  diagnostics: flow-diag
  display:     ${DISPLAY_MODE}

Next:
  1. Edit ${FLOW_HOME}/.env and fill API keys (keep mode 600).
  2. Check hardware:   sudo systemctl restart flow-hal
     journalctl -u flow-hal -n 80 --no-pager
  3. Start backend:   sudo systemctl start flow-backend
     curl -s http://127.0.0.1:8000/healthz | jq
  4. Reboot the Pi:   sudo reboot
  5. After reboot:    systemctl status flow-hal flow-backend flow-ui
  6. Support bundle:  sudo flow-diag

If this is a Desktop image, T01 expects Lite; the kiosk unit may
conflict with the desktop session. See docs/deployment/T01-hardware-runbook.md.
EOF
