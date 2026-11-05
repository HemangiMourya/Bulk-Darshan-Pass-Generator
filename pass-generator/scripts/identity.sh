#!/usr/bin/env bash
# =============================================================================
# identity.sh – Student Identity Verification
# Prints student info and Azure account details for lab submission.
# =============================================================================
set -euo pipefail

# ╔══════════════════════════════════════════════════╗
# ║   STUDENT DETAILS                                ║
# ╚══════════════════════════════════════════════════╝
STUDENT_NAME="Hemangi Mourya"

echo "==========================================="
echo "=== STUDENT IDENTITY VERIFICATION ==="
echo "==========================================="
echo ""
echo "Student Name : ${STUDENT_NAME}"
echo "OS User      : $(whoami)"
echo "Hostname     : $(hostname)"
echo "Date         : $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""
echo "--- Azure Account Info ---"
az account show --query "{Azure_Email: user.name, Subscription_ID: id}" -o table 2>/dev/null || echo "[Note: Run 'az login' to display Azure subscription info]"
echo ""
echo "==========================================="
