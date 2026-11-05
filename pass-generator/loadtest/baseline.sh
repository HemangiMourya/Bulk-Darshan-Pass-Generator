#!/usr/bin/env bash
# =============================================================================
# baseline.sh – Light baseline traffic
# Sends ~2 requests/second for 2 minutes for "before load" verification screenshots.
#
# Usage: ./baseline.sh <EXTERNAL_IP>
# Requires: hey (https://github.com/rakyll/hey)
# =============================================================================
set -euo pipefail

EXTERNAL_IP="${1:?Usage: $0 <EXTERNAL_IP>}"
URL="http://${EXTERNAL_IP}/load?n=10&unique=1"

echo "============================================"
echo " Baseline Traffic – ~2 req/s for 2 minutes"
echo " Target: ${URL}"
echo " Start:  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================"

# -q 2 = 2 requests per second per worker, -c 1 = 1 concurrent worker
hey -z 120s -c 1 -q 2 "${URL}"

echo ""
echo "============================================"
echo " End: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================"
