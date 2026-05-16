# operations

FastAPI + Temporal + Rust solvers (assignment_solver).

## Local development

### Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Rust toolchain (for building `assignment_solver`)

### Start infrastructure

```bash
# from repo root
docker compose -f docker-compose.dev.yml up -d
```

Services:

| Service | URL |
|---|---|
| Temporal server (gRPC) | `localhost:7233` |
| Temporal UI | http://localhost:8233 |
| Redis | `localhost:6379` |

Wait ~15 s for Temporal to finish schema migration before starting the worker.

### Install Python dependencies

```bash
cd apps/api
pip install temporalio "redis>=5.0.0"
# or: rye sync
```

### Run API server

```bash
cd apps/api
python -m src.operations.main
```

### Run Temporal worker

```bash
cd apps/api
python -m src.worker.main
```

### Stop infrastructure

```bash
docker compose -f docker-compose.dev.yml down
```

---

## Kubernetes deployment

### Prerequisites

- `kubectl` configured against your cluster
- `helm` 3+
- A container registry accessible from the cluster

### 1. Deploy Temporal server

Use the official Helm charts — **do not install manually**:

```bash
helm repo add temporalio https://go.temporal.io/helm-charts
helm repo update

# Minimal dev/staging install (uses Cassandra by default; swap backend as needed)
helm install temporal temporalio/temporal \
  --namespace temporal --create-namespace \
  --set server.replicaCount=1 \
  --timeout 15m
```

Reference: https://github.com/temporalio/helm-charts

### 2. Deploy Redis

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install redis bitnami/redis \
  --namespace redis --create-namespace \
  --set auth.enabled=false \
  --set replica.replicaCount=0
```

### 3. Build and push the application image

```bash
# from apps/api/
docker build -t <REGISTRY>/operations:latest .
docker push <REGISTRY>/operations:latest
```

### 4. Configure

Edit `deploy/charts/backend/values.yaml` and `deploy/charts/worker/values.yaml`
if your Temporal/Redis service names differ.

### 5. Deploy via Helm

```bash
# from repo root
helm install backend deploy/charts/backend
helm install worker  deploy/charts/worker
```

### 6. Verify

```bash
kubectl get pods
kubectl logs -l app.kubernetes.io/name=api
kubectl logs -l app.kubernetes.io/name=worker
```

### Architecture

```
                 ┌───────────────────────────────────────────────────┐
Internet ──────► │  Service/Ingress :8000                            │
                 │  Deployment: api  (replicas: 1)                   │
                 │  - POST /solve, /experiment1..4                   │
                 │  - WS  /jobs/{id}/events                          │
                 │  - GET/DELETE /jobs/{id}                          │
                 └──────────────────┬────────────────────────────────┘
                                    │ gRPC
                 ┌──────────────────▼────────────────────────────────┐
                 │  Temporal server (helm-charts)                    │
                 └──────────────────┬────────────────────────────────┘
                                    │ poll
                 ┌──────────────────▼────────────────────────────────┐
                 │  Deployment: worker  (HPA: 1–5 replicas)          │
                 │  - SolveWorkflow, ExperimentWorkflow               │
                 │  - run_algorithm_activity (Rust solver)           │
                 │  - generate_experiment_runs_activity              │
                 └──────────────────┬────────────────────────────────┘
                                    │ pub/sub (iterations)
                 ┌──────────────────▼────────────────────────────────┐
                 │  Redis (bitnami/redis)                            │
                 └───────────────────────────────────────────────────┘
```

### Scaling notes

- **API**: stateless, scale replicas freely.
- **Worker**: each pod runs Rust+Rayon solvers that saturate available CPU cores.
  With `concurrency=1` (default), one pod handles one activity at a time.
  HPA scales out pods to increase parallel task throughput.
  Scale based on Temporal task queue backlog for more precise control
  (requires `keda` with Temporal scaler).
- **Temporal server**: managed separately via helm-charts; consult
  https://github.com/temporalio/helm-charts for production configuration.
