#!/usr/bin/env bash
# Run 6 article generations every 5 minutes.
# Logs go to logs/.
set -u
cd "$(dirname "$0")/.."
source ~/.env  # OPENAI_API_KEY, OPENROUTER_API_KEY, SIMPLEMESSAGE_API_KEY

mkdir -p logs
START=$(date +%s)
echo "[runner] started PID=$$ at $(date)" >> logs/runner.log

for i in 0 1 2 3 4 5; do
  TS=$(date +%H%M%S)
  LOG="logs/article-${i}-${TS}.log"
  echo "[runner] launching topic #${i} -> ${LOG}" >> logs/runner.log
  python3 auto/article.py "${i}" >> "${LOG}" 2>&1
  echo "[runner] topic #${i} exit=$? at $(date)" >> logs/runner.log

  if [ "${i}" -lt 5 ]; then
    # sleep until next 5-minute slot from START
    NEXT=$(( START + ( i + 1 ) * 300 ))
    NOW=$(date +%s)
    SLEEP=$(( NEXT - NOW ))
    [ "${SLEEP}" -gt 0 ] && sleep "${SLEEP}"
  fi
done

echo "[runner] done at $(date)" >> logs/runner.log
