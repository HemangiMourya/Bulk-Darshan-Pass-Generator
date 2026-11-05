#!/usr/bin/env bash
# =============================================================================
# loadtest.sh – Ramped load test using 'hey'
# Sends increasing concurrency against /load?n=100&unique=1
# Total duration: ~3 minutes (NEVER more than 5 minutes to protect cloud credits)
#
# Usage: ./loadtest.sh <EXTERNAL_IP>
# Requires: hey (https://github.com/rakyll/hey)
# =============================================================================
set -euo pipefail

EXTERNAL_IP="${1:?Usage: $0 <EXTERNAL_IP>}"
URL="http://${EXTERNAL_IP}/load?n=100&unique=1"

echo "============================================"
echo " Load Test – Ramped Concurrency"
echo " Target: ${URL}"
echo " Start:  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================"

# Phase 1: warm-up – 30 seconds at concurrency 5
echo ""
echo ">>> Phase 1: 30s at concurrency 5"
hey -z 30s -c 5 "${URL}"

# Phase 2: medium load – 60 seconds at concurrency 20
echo ""
echo ">>> Phase 2: 60s at concurrency 20"
hey -z 60s -c 20 "${URL}"

# Phase 3: heavy load – 90 seconds at concurrency 40
echo ""
echo ">>> Phase 3: 90s at concurrency 40"
hey -z 90s -c 40 "${URL}"

echo ""
echo "============================================"
echo " End: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================"
