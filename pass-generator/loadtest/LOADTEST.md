# Load Testing Guide — MandirMitra Pass Generator

## Prerequisites

- `hey` installed ([github.com/rakyll/hey](https://github.com/rakyll/hey))
- OR `locust` installed (`pip install locust`)
- The app is deployed to AKS and the LoadBalancer EXTERNAL-IP is known

Get the external IP:

```bash
kubectl get svc pass-frontend-svc -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

---

## Terminal Setup

Open **three terminals** side by side:

### Terminal 1 – Watch HPA

```bash
kubectl get hpa pass-frontend-hpa -w
```

This displays the replica count and CPU % updating in real time.

### Terminal 2 – Watch Pods

```bash
kubectl get pods -l app=pass-frontend -w
```

This displays new pods being created during scale-up and terminated during scale-down.

### Terminal 3 – Run Load Test

Choose ONE of the options below.

---

## Option A: `hey` (Recommended for Simplicity)

### Step 1: Baseline (Before-load Screenshots)

```bash
# ~2 req/s for 2 minutes
bash loadtest/baseline.sh <EXTERNAL_IP>
```

Capture screenshots of Terminal 1 and 2 after this finishes (HPA should show low CPU ~5-15%, 1 replica).

### Step 2: Ramped Load Test

```bash
# 30s @ c=5, 60s @ c=20, 90s @ c=40 – total ~3 minutes
bash loadtest/loadtest.sh <EXTERNAL_IP>
```

Watch Terminal 1 and 2: you should see replicas scale from 1 → 3-5 pods within 1-2 minutes as CPU exceeds 50%. Capture screenshots during peak load.

### Step 3: Cool-Down & Scale-Down

After the load test ends, keep watching Terminals 1 & 2. Due to `scaleDown.stabilizationWindowSeconds: 120`, replicas will start scaling down after ~2 minutes. Capture screenshots showing scale-down back to 1 replica.

---

## Option B: Locust (Richer UI & Detailed Metrics)

```bash
# CLI mode – capped at 5 minutes
locust -f loadtest/locustfile.py \
       --host http://<EXTERNAL_IP> \
       --run-time 5m \
       --headless \
       -u 20 -r 5

# OR web UI mode (open http://localhost:8089)
locust -f loadtest/locustfile.py --host http://<EXTERNAL_IP>
```

> ⚠️ **IMPORTANT**: Never run load tests for more than 5 minutes to stay safely within Azure free-tier budgets.

---

## Expected Timeline

| Time       | Event                                  |
|------------|----------------------------------------|
| 0:00-0:30  | Warm-up (c=5), CPU rises steadily      |
| 0:30-1:30  | Medium load (c=20), HPA triggers       |
| 1:00-2:00  | New pods scheduled & become Ready      |
| 1:30-3:00  | Heavy load (c=40), 3-5 replicas active |
| 3:00-5:00  | Cool-down, scale-down after 2 min      |
