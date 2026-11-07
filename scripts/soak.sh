#!/usr/bin/env bash
# T29 short soak wrapper; run against a mock backend.
set -euo pipefail
SECONDS_TO_RUN="${1:-3600}"
INTERVAL="${2:-5}"
echo "soak for ${SECONDS_TO_RUN}s, sampling every ${INTERVAL}s"
END=$((SECONDS + SECONDS_TO_RUN))
while [ "${SECONDS}" -lt "${END}" ]; do
  pid="$(pgrep -f 'python -m service' | head -n1 || true)"
  if [ -n "${pid}" ]; then
    rss="$(awk '/VmRSS/ {print $2}' "/proc/${pid}/status" 2>/dev/null || echo 0)"
    fds="$(ls "/proc/${pid}/fd" 2>/dev/null | wc -l)"
    echo "$(date -Is) rss_kb=${rss} fds=${fds}"
  else
    echo "$(date -Is) backend not running"
  fi
  sleep "${INTERVAL}"
done
