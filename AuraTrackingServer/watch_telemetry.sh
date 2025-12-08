#!/bin/bash
set -o pipefail

STATE_FILE=".last_time"
SLEEP_OK=1
SLEEP_FAIL=3

if [ -f "$STATE_FILE" ]; then
  last_time=$(cat "$STATE_FILE")
else
  last_time="1970-01-01 00:00:00+00"
fi

while true; do
  rows=$(docker exec aura_timescaledb \
    psql -U aura -d auratracking -At -c "
      SELECT time, device_id, message_id
      FROM telemetry
      WHERE time > '$last_time'
      ORDER BY time ASC;
    " 2>/dev/null)

  if [ $? -ne 0 ]; then
    echo "[WARN] Timescale indisponível — aguardando..."
    sleep $SLEEP_FAIL
    continue
  fi

  if [ -n "$rows" ]; then
    echo "$rows"
    last_time=$(echo "$rows" | tail -n1 | cut -d'|' -f1)
    echo "$last_time" > "$STATE_FILE"
  fi

  sleep $SLEEP_OK
done
