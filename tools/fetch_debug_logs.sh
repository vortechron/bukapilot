#!/usr/bin/env bash
# Fetch debug logs from KA2 dongle via SSH
# Usage: ./tools/fetch_debug_logs.sh [output_dir]

DONGLE_IP="${DONGLE_IP:-192.168.0.64}"
DONGLE_USER="${DONGLE_USER:-kommu}"
OUT_DIR="${1:-./debug_logs}"

mkdir -p "$OUT_DIR"

echo "Fetching debug logs from $DONGLE_USER@$DONGLE_IP ..."
scp "$DONGLE_USER@$DONGLE_IP":/tmp/bp_debug_*.jsonl "$OUT_DIR/" 2>/dev/null
scp "$DONGLE_USER@$DONGLE_IP":/tmp/bp_debug_*.jsonl.1 "$OUT_DIR/" 2>/dev/null

echo "Logs saved to $OUT_DIR/"
ls -lh "$OUT_DIR"/bp_debug_* 2>/dev/null || echo "No logs found."
