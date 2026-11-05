#!/usr/bin/env bash
# =============================================================================
# deploy.sh – Print (not auto-execute) all Azure deployment commands
# Edit variables below if needed, then copy-paste commands into your terminal.
# =============================================================================
set -euo pipefail

# ╔══════════════════════════════════════════════════╗
# ║   DEPLOYMENT VARIABLES                           ║
# ╚══════════════════════════════════════════════════╝
RESOURCE_GROUP="mandirmitra-rg"
LOCATION="eastus"
ACR_NAME="mandirmitraacr"          # Must be globally unique, alphanumeric lowercase
AKS_CLUSTER="mandirmitra-aks"
NODE_SIZE="Standard_B2s"
NODE_COUNT=1
IMAGE_NAME="pass-frontend"
IMAGE_TAG="v1"

echo "==========================================="
echo "  MandirMitra Deployment Commands"
echo "  (Copy-paste commands into terminal)"
echo "==========================================="

cat << 'HEADER'

# -----------------------------------------------
# Step 1: Create Resource Group
# -----------------------------------------------
HEADER
echo "az group create --name ${RESOURCE_GROUP} --location ${LOCATION}"

cat << 'HEADER'

# -----------------------------------------------
# Step 2: Create Azure Container Registry (ACR)
# -----------------------------------------------
HEADER
echo "az acr create --resource-group ${RESOURCE_GROUP} --name ${ACR_NAME} --sku Basic"

cat << 'HEADER'

# -----------------------------------------------
# Step 3: Build and push image to ACR using ACR Tasks
# (No local Docker daemon required)
# -----------------------------------------------
HEADER
echo "az acr build --registry ${ACR_NAME} --image ${IMAGE_NAME}:${IMAGE_TAG} ./frontend"

cat << 'HEADER'

# -----------------------------------------------
# Step 4: Create 1-node AKS cluster with ACR attached
# -----------------------------------------------
HEADER
echo "az aks create \\"
echo "  --resource-group ${RESOURCE_GROUP} \\"
echo "  --name ${AKS_CLUSTER} \\"
echo "  --node-count ${NODE_COUNT} \\"
echo "  --node-vm-size ${NODE_SIZE} \\"
echo "  --attach-acr ${ACR_NAME} \\"
echo "  --generate-ssh-keys"

cat << 'HEADER'

# -----------------------------------------------
# Step 5: Get Kubernetes credentials
# -----------------------------------------------
HEADER
echo "az aks get-credentials --resource-group ${RESOURCE_GROUP} --name ${AKS_CLUSTER}"

cat << 'HEADER'

# -----------------------------------------------
# Step 6: Update ACR placeholder in deployment manifest
# -----------------------------------------------
HEADER
echo "sed -i 's/<ACR_NAME>/${ACR_NAME}/g' k8s/deployment.yaml"

cat << 'HEADER'

# -----------------------------------------------
# Step 7: Apply all Kubernetes manifests
# -----------------------------------------------
HEADER
echo "kubectl apply -f k8s/"

cat << 'HEADER'

# -----------------------------------------------
# Step 8: Watch for LoadBalancer External IP
# -----------------------------------------------
HEADER
echo "kubectl get svc pass-frontend-svc -w"
