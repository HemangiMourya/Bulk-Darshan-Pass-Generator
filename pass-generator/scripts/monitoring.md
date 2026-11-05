# Monitoring Setup Guide — MandirMitra Pass Generator

Step-by-step instructions for configuring Azure Monitor, Container Insights, alert rules, and dashboards. These are **manual configuration steps** designed to comply with free-tier resource bounds.

---

## 1. Enable Container Insights

### 1.1 Create a Log Analytics Workspace

```bash
az monitor log-analytics workspace create \
  --resource-group mandirmitra-rg \
  --workspace-name mandirmitra-logs \
  --location eastus
```

### 1.2 Enable Container Insights on the AKS Cluster

```bash
# Retrieve Workspace Resource ID
WORKSPACE_ID=$(az monitor log-analytics workspace show \
  --resource-group mandirmitra-rg \
  --workspace-name mandirmitra-logs \
  --query id -o tsv)

# Enable monitoring addon
az aks enable-addons \
  --resource-group mandirmitra-rg \
  --name mandirmitra-aks \
  --addons monitoring \
  --workspace-resource-id "$WORKSPACE_ID"
```

### 1.3 Data Collection Optimization (Save Free-Tier Quota)

To ensure we do not exhaust the daily free-tier Log Analytics quota (500 MB/day), configure metrics collection only:

1. In the **Azure Portal**, navigate to **AKS cluster → Monitoring → Insights**.
2. Click **Configure monitoring** (Data Collection Rule).
3. Under **Logs and events**:
   - Set Container logs to **None** (disable stdout/stderr ingestion).
   - Retain **Performance Counters** and **Insights Metrics**.

---

## 2. Configure Action Group (Email Alerts)

Create an Action Group to receive automated notifications when alert rules trigger:

```bash
az monitor action-group create \
  --resource-group mandirmitra-rg \
  --name mandirmitra-alerts \
  --short-name "MandirAlerts" \
  --action email admin "devotee-admin@example.com"
```

---

## 3. Configure Alert Rules

### Alert 1: High CPU Utilization (> 75% for 5 minutes)

Triggers during sustained traffic surges when pods require horizontal autoscaling:

- **Signal:** InsightsMetrics (CPU utilization % per container)
- **Threshold:** > 75%
- **Evaluation Period:** 5 minutes
- **Action:** Send email via `mandirmitra-alerts` Action Group

### Alert 2: Excessive Pod Restarts (> 3 in 10 minutes)

Detects application crashes or Out-Of-Memory (OOM) conditions:

- **Signal:** KQL Query on KubePodInventory
- **Threshold:** Restarts > 3
- **Period:** 10 minutes

---

## 4. Azure Monitor Dashboard KQL Queries

Use these queries to populate tiles on your Azure Monitor Dashboard:

### Tile 1: Average CPU Utilization per Pod (%)
```kusto
InsightsMetrics
| where Namespace == "container.azm.ms/cpu" and Name == "usageNanoCores"
| where Val > 0
| extend PodName = tostring(split(Tags, '"pod": "')[1])
| summarize AvgCPU = avg(Val) / 10000000 by bin(TimeGenerated, 1m), PodName
| render timechart
```

### Tile 2: Memory Working Set Trends (MB)
```kusto
InsightsMetrics
| where Namespace == "container.azm.ms/memory" and Name == "workingSetBytes"
| extend PodName = tostring(split(Tags, '"pod": "')[1])
| summarize MemoryMB = avg(Val) / 1048576 by bin(TimeGenerated, 1m), PodName
| render timechart
```

### Tile 3: Total HTTP Request Count & Latency
```kusto
InsightsMetrics
| where Origin == "container.azm.ms/prometheus"
| where Name in ("http_requests_total", "http_request_duration_seconds")
| summarize Count = count() by bin(TimeGenerated, 1m), Name
| render timechart
```

### Tile 4: Active Replica Count During Auto-Scaling
```kusto
KubePodInventory
| where ControllerName == "pass-frontend"
| summarize ActiveReplicas = dcount(PodUid) by bin(TimeGenerated, 1m)
| render timechart
```
