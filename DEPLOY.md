# Deployment Guide

## Prerequisites

Install these cluster-wide components **once per cluster** before applying
any application manifests.  These are cluster operator tasks — do not run
them in CI/CD pipelines.

### 1. ingress-nginx

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace
```

Wait for the controller to be ready and note the external IP:

```bash
kubectl get svc -n ingress-nginx ingress-nginx-controller
```

> Docs: https://kubernetes.github.io/ingress-nginx/deploy/

### 2. cert-manager

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set crds.enabled=true
```

> Docs: https://cert-manager.io/docs/installation/helm/

### 3. DNS

Point your domain's A-record to the external IP of `ingress-nginx-controller`
before applying the Ingress (cert-manager needs HTTP-01 challenge to succeed).

---

## Before First Deploy

1. **Fill in TODOs** in the manifests:

   | File | TODO |
   |---|---|
   | `k8s/frontend-ingress.yaml` | Replace `TODO_YOUR_DOMAIN` with your domain (2 places) |
   | `k8s/cluster-issuer.yaml` | Replace `TODO_YOUR_EMAIL` with your email |
   | `k8s/frontend-deployment.yaml` | Replace `<REGISTRY>/coursework-ui:latest` with your image (2 places: initContainer + main container) |
   | `k8s/api-deployment.yaml` | Replace `<REGISTRY>/coursework-operations:latest` |
   | `k8s/worker-deployment.yaml` | Same |

2. **Build and push the images:**

   ```bash
   # Frontend (one image for all envs — no build-time URL args)
   docker build -t <REGISTRY>/coursework-ui:latest apps/ui/
   docker push <REGISTRY>/coursework-ui:latest

   # Backend / worker (same image, different CMD)
   docker build -t <REGISTRY>/coursework-operations:latest apps/api/
   docker push <REGISTRY>/coursework-operations:latest
   ```

---

## Apply Order

Apply in this order — dependencies must exist before dependents.

```bash
# 1. Cluster-scoped resources (once per cluster, requires cert-manager CRDs)
kubectl apply -f k8s/cluster-issuer.yaml

# 2. Backend infrastructure config
kubectl apply -f k8s/configmap.yaml

# 3. Backend services
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/api-service.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/worker-hpa.yaml

# 4. Frontend
kubectl apply -f k8s/frontend-configmap.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml

# 5. Ingress (last — backend and frontend services must exist first)
kubectl apply -f k8s/frontend-ingress.yaml
```

### Verify

```bash
# All pods running
kubectl get pods

# Certificate issued (may take 1–2 min on first deploy)
kubectl get certificate
kubectl describe certificate coursework-tls

# Ingress has an address
kubectl get ingress coursework-ingress

# Smoke test
curl -si https://YOUR_DOMAIN/
curl -si https://YOUR_DOMAIN/config.js   # must contain apiBaseUrl: "/api"
curl -I  https://YOUR_DOMAIN/config.js   # must have Cache-Control: no-store
```

---

## Runtime Config Changes (no image rebuild)

All environment-specific settings live in `k8s/frontend-configmap.yaml`.
Changing them requires only a ConfigMap update + pod restart.

### Roll back USE_TEMPORAL_API

```bash
# Edit the ConfigMap
kubectl edit configmap frontend-config

# Change: APP_USE_TEMPORAL_API: "true"  →  APP_USE_TEMPORAL_API: "false"

# Restart pods to pick up the new value (initContainer re-runs on each pod start)
kubectl rollout restart deployment/frontend

# Watch rollout
kubectl rollout status deployment/frontend
```

### Change API base URL

```bash
kubectl patch configmap frontend-config \
  --type merge \
  -p '{"data":{"APP_API_BASE_URL":"/api-v2"}}'

kubectl rollout restart deployment/frontend
```

> **Why restart?**  `window.__APP_CONFIG__` is baked into `config.js` by
> `docker-entrypoint.sh` (or the initContainer in k8s) at **pod start time**,
> not at request time.  A pod restart re-runs the initContainer and generates
> a fresh `config.js`.  The `Cache-Control: no-store` header on `/config.js`
> ensures browsers always fetch the latest version.

---

## Ingress WebSocket Notes

Long-running WebSocket connections (`/api/jobs/{id}/events`) are kept alive
by the timeout annotations in `frontend-ingress.yaml`:

```yaml
nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
```

These are set to 1 hour.  Experiments that run longer than 1 hour will need
these values increased.

---

## Teardown

```bash
kubectl delete -f k8s/frontend-ingress.yaml
kubectl delete -f k8s/frontend-service.yaml
kubectl delete -f k8s/frontend-deployment.yaml
kubectl delete -f k8s/frontend-configmap.yaml
kubectl delete -f k8s/api-service.yaml
kubectl delete -f k8s/api-deployment.yaml
kubectl delete -f k8s/worker-deployment.yaml
kubectl delete -f k8s/worker-hpa.yaml
kubectl delete -f k8s/configmap.yaml
# ClusterIssuer is cluster-scoped — delete manually if no longer needed:
# kubectl delete clusterissuer letsencrypt-prod
```
