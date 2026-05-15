# coursework-operations

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
python -m src.coursework_operations.main
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
