#!/usr/bin/env bash
# Configure the Raspberry Pi boot display for the Flow canvas.
# Usage: sudo flow-display hdmi1024x600|hdmi1280x800|hdmi720|dsi|none|--remove
#
# Pick the mode that matches the panel, not the CSS canvas:
#   hdmi1024x600   7" 1024x600 panel on an RTD2660TP driver board (default HW)
#   hdmi1280x800   10.1" 16:10 HDMI panel on an RTD2660 driver board
#   hdmi720        7" square panel that accepts a 720x720 custom mode
#   dsi            DSI panel, keep its EDID/native mode
#   none           remove the managed block, back to the native mode
set -euo pipefail

MODE="${1:-hdmi720}"
CONFIG=""
for candidate in /boot/firmware/config.txt /boot/config.txt; do
  if [ -f "${candidate}" ]; then
    CONFIG="${candidate}"
    break
  fi
done
if [ -z "${CONFIG}" ]; then
  echo "flow-display: cannot find /boot/firmware/config.txt" >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "flow-display: run with sudo" >&2
  exit 1
fi

BEGIN="# >>> flow display managed >>>"
END="# <<< flow display managed <<<"
BACKUP="${CONFIG}.flow-backup.$(date +%Y%m%d-%H%M%S)"
cp -a "${CONFIG}" "${BACKUP}"

# Remove a previous managed block idempotently.
awk -v begin="${BEGIN}" -v end="${END}" '
  $0 == begin { skip = 1; next }
  $0 == end   { skip = 0; next }
  !skip       { print }
' "${CONFIG}" > "${CONFIG}.flow-new"
mv "${CONFIG}.flow-new" "${CONFIG}"

if [ "${MODE}" = "--remove" ] || [ "${MODE}" = "none" ]; then
  echo "flow-display: managed block removed; backup=${BACKUP}"
  exit 0
fi

case "${MODE}" in
  hdmi720)
    cat >> "${CONFIG}" <<'EOF'
# >>> flow display managed >>>
# T01: 720x720 HDMI canvas. Revert with: sudo flow-display none
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=720 720 60 6 0 0 0
disable_overscan=1
# <<< flow display managed <<<
EOF
    ;;
  hdmi1024x600)
    cat >> "${CONFIG}" <<'EOF'
# >>> flow display managed >>>
# T01: 1024x600 HDMI mode for the 7" RT2660TP board (50-pin TTL panel,
# sticker: RT2660TP / 7寸 / 1024*600 / 50PTTL). Revert with:
# sudo flow-display none
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=1024 600 60 6 0 0 0
disable_overscan=1
# <<< flow display managed <<<
EOF
    ;;
  hdmi1280x800)
    cat >> "${CONFIG}" <<'EOF'
# >>> flow display managed >>>
# T01: 1280x800 HDMI mode for 10.1" 16:10 panels (RTD2660 class driver
# boards). Revert with: sudo flow-display none
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=1280 800 60 6 0 0 0
disable_overscan=1
# <<< flow display managed <<<
EOF
    ;;
  dsi)
    cat >> "${CONFIG}" <<'EOF'
# >>> flow display managed >>>
# DSI panel: keep the panel's native mode; T05 uses a 720x720 CSS canvas.
disable_overscan=1
# <<< flow display managed <<<
EOF
    ;;
  *)
    echo "flow-display: expected hdmi1024x600, hdmi1280x800, hdmi720, dsi or none" >&2
    exit 2
    ;;
esac

echo "flow-display: ${MODE} written to ${CONFIG}"
echo "flow-display: reboot required; backup=${BACKUP}"
