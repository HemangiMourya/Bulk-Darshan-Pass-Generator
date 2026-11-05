#!/usr/bin/env bash
# =============================================================================
# cleanup.sh – Print (not auto-execute) cleanup commands
# Deleting the resource group removes ALL cloud resources (ACR, AKS, VNet, Disks).
# =============================================================================
set -euo pipefail

# ╔══════════════════════════════════════════════════╗
# ║   RESOURCE GROUP TO DELETE                       ║
# ╚══════════════════════════════════════════════════╝
RESOURCE_GROUP="mandirmitra-rg"

echo "==========================================="
echo "  Cleanup Commands (Copy-paste to run)"
echo "==========================================="
echo ""
echo "# Delete ALL cloud resources by removing the resource group"
echo "az group delete --name ${RESOURCE_GROUP} --yes --no-wait"
echo ""
echo "# Verify deletion status"
echo "az group list -o table | grep ${RESOURCE_GROUP}"
echo ""
echo "# Clean up local kubectl cluster context"
echo "kubectl config delete-context mandirmitra-aks || true"
echo ""
echo "==========================================="
echo "  WARNING: Deletion is permanent!"
echo "==========================================="
