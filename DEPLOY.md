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

1. **Fill in TODOs** in the chart values and cluster manifest:

   | File | TODO |
   |---|---|
   | `deploy/cluster-issuer.yaml` | Replace `TODO_YOUR_EMAIL` with your email |
   | `deploy/charts/frontend/values.yaml` | Replace `TODO_YOUR_DOMAIN` in `ingress.host` |

2. **Build and push the images:**

   ```bash
   # Frontend (one image for all envs — no build-time URL args)
   docker build -t <REGISTRY>/ui:latest apps/ui/
   docker push <REGISTRY>/ui:latest

   # Backend / worker (same image, different CMD)
   docker build -t <REGISTRY>/operations:latest apps/api/
   docker push <REGISTRY>/operations:latest
   ```

---

## Deploy

### First deploy

```bash
# 1. Cluster-scoped resources (once per cluster, requires cert-manager CRDs)
kubectl apply -f deploy/cluster-issuer.yaml

# 2–4. Install Helm charts (order matters: backend before worker before frontend)
helm install backend  deploy/charts/backend
helm install worker   deploy/charts/worker
helm install frontend deploy/charts/frontend
```

### Upgrade (subsequent deploys)

```bash
helm upgrade backend  deploy/charts/backend
helm upgrade worker   deploy/charts/worker
helm upgrade frontend deploy/charts/frontend
```

Or upgrade only the changed chart:

```bash
helm upgrade frontend deploy/charts/frontend --reuse-values
```

### Verify

```bash
# All pods running
kubectl get pods

# Certificate issued (may take 1–2 min on first deploy)
kubectl get certificate
kubectl describe certificate tls

# Ingress has an address
kubectl get ingress

# Smoke test
curl -si https://YOUR_DOMAIN/
curl -si https://YOUR_DOMAIN/config.js   # must contain apiBaseUrl: "/api"
curl -I  https://YOUR_DOMAIN/config.js   # must have Cache-Control: no-store
```

---

## CI/CD Pipeline

### How it works

```
PR opened / push to main
  └─ ci.yml
       ├─ detect-changes  (dorny/paths-filter)
       ├─ test            (eslint+tsc | pytest, matrix, path-filtered)
       └─ build-check     (PR only: docker build --no-push, layer cache)

merge to main (push)
  └─ ci.yml  (tests again — same as above)
  └─ cd.yml
       ├─ detect-changes
       ├─ test            (same gate — image never pushed if tests red)
       ├─ build-push      → ghcr.io/<owner>/diploma-<component>:<sha8>
       │                    immutable tag, never 'latest'
       └─ writeback       → sed image.tag in deploy/charts/<comp>/values.yaml
                            git commit "[skip ci]" + rebase + push
                            Argo CD detects values.yaml change → auto-sync
```

### Path filters (what triggers each component)

| Component | Paths that trigger rebuild |
|---|---|
| `frontend` | `apps/ui/**` |
| `backend`  | `apps/api/**`, `libs/operations/**`, `apps/worker/**` |
| `worker`   | `apps/worker/**`, `libs/operations/**` |

A commit touching only `apps/ui/` rebuilds frontend only — backend and worker
are not rebuilt.

### Image naming

| Component | Image |
|---|---|
| frontend | `ghcr.io/kulunchick/diploma-frontend:<sha8>` |
| backend  | `ghcr.io/kulunchick/diploma-backend:<sha8>`  |
| worker   | `ghcr.io/kulunchick/diploma-worker:<sha8>`   |

`<sha8>` = first 8 characters of the merge commit SHA.  Immutable.
`latest` is never used or pushed anywhere.

### Write-back anti-loop protection

Two layers prevent infinite CI loops from the write-back commit:

1. **GITHUB_TOKEN push** — GitHub skips re-triggering workflows for commits
   pushed by a workflow using the built-in `GITHUB_TOKEN`.
2. **`[skip ci]` in the commit message** — belt-and-suspenders; even if the
   first layer ever changes, `[skip ci]` tells GitHub Actions to skip.

---

## ⚠️ Branch Protection — TODO

If `main` is branch-protected (required status checks, no direct push), the
write-back `git push origin main` in `cd.yml` will be rejected with a 403.

**Choose one of the following options and configure it:**

### Option A — Exempt the `github-actions[bot]` actor (recommended for simplicity)

In GitHub → Settings → Branches → Protection rules for `main`:
- Enable "Allow specified actors to bypass required pull requests"
- Add `github-actions[bot]`

This allows the write-back push while still requiring PRs for human commits.
No external secrets or GitHub Apps needed.

### Option B — Write-back via auto-merge PR

Replace the direct `git push` in the `writeback` job with:
```bash
# Create a branch, push, open a PR, auto-merge
BRANCH="cd/bump-${GITHUB_SHA::8}"
git checkout -b "${BRANCH}"
git push origin "${BRANCH}"
gh pr create --title "chore(cd): bump to ${SHA} [skip ci]" \
             --body "Automated image tag bump" \
             --base main --head "${BRANCH}"
gh pr merge "${BRANCH}" --auto --squash --delete-branch
```

Requires:
- `gh` CLI (available on ubuntu-latest runners)
- `pull-requests: write` permission added to `cd.yml`
- Auto-merge enabled on the repository

More complex but works with any branch protection setup.

**Current state:** direct push is implemented. If main is not protected (common
for solo/small-team projects), this works as-is.

---

## imagePullSecret — ghcr.io private packages

By default, ghcr.io packages are **private**.  Kubernetes needs credentials to
pull them.

### Option A — Make packages public

In GitHub → Packages → each package → Package settings → Visibility → Public.

Acceptable for the `frontend` image (static files, no secrets).
Consider carefully for `backend` / `worker` (they embed no secrets, but
expose internal package names and dependency versions).

### Option B — imagePullSecret in the cluster (recommended)

Create a Kubernetes secret once per namespace:

```bash
kubectl create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username=<github-username> \
  --docker-password=<PAT-with-read:packages> \
  --docker-email=<email> \
  --namespace=<your-namespace>
```

Then reference it in each Helm chart's `values.yaml`:

```yaml
# deploy/charts/frontend/values.yaml
imagePullSecrets:
  - name: ghcr-pull-secret
```

Do the same for `backend` and `worker` charts.

The `imagePullSecrets` field is already present (commented out) in all three
`values.yaml` files — just uncomment and set the name.

> **Secret management**: the PAT used for the pull secret should be stored in a
> secret manager (Vault, AWS Secrets Manager, etc.) and rotated periodically.
> Creating the actual Kubernetes secret is an operator task, not automated here.

---

## Runtime Config Changes (no image rebuild)

All environment-specific settings live in `deploy/charts/*/values.yaml`.

### Roll back USE_TEMPORAL_API via Helm chart

```bash
# Edit the chart value
helm upgrade <release> deploy/charts/frontend \
  --set config.useTemporalApi=false \
  --reuse-values

# Or directly edit the values.yaml and let Argo CD sync:
sed -i 's/useTemporalApi: "true"/useTemporalApi: "false"/' \
  deploy/charts/frontend/values.yaml
git add deploy/charts/frontend/values.yaml
git commit -m "chore: disable temporal API [skip ci]"
git push origin main
```

Argo CD detects the values.yaml change and syncs within seconds.
No image rebuild needed.

### Change API base URL

```bash
sed -i 's|apiBaseUrl: "/api"|apiBaseUrl: "/api-v2"|' \
  deploy/charts/frontend/values.yaml
git add deploy/charts/frontend/values.yaml
git commit -m "chore: update api base url [skip ci]"
git push origin main
```

> **Why restart?**  `window.__APP_CONFIG__` is baked into `config.js` by
> the initContainer at **pod start time**.  A values.yaml change triggers
> Argo CD to roll out a new pod, which re-runs the initContainer with the
> new values.

---

## Manual Rollback (image tag regression)

If a bad image was deployed and you need to revert **without** waiting for a
new code fix:

### Option 1 — Revert the write-back commit (recommended)

```bash
# Find the write-back commit
git log --oneline deploy/charts/frontend/values.yaml

# e.g.: abc12345 chore(cd): bump image tags to deadbeef [skip ci]
# Revert it:
git revert <commit-sha> --no-edit
git push origin main
# Argo CD syncs within seconds, rolls back to the previous image tag.
```

### Option 2 — Direct patch (faster, no git history)

```bash
# Pin to a known-good tag
sed -i "s/^  tag: .*$/  tag: <known-good-sha8>/" \
  deploy/charts/frontend/values.yaml
git add deploy/charts/frontend/values.yaml
git commit -m "fix(cd): revert frontend to <known-good-sha8> [skip ci]"
git push origin main
```

### Option 3 — Argo CD override (temporary, non-GitOps)

```bash
# Force a specific image in the running deployment (bypasses GitOps)
kubectl set image deployment/frontend-<release> \
  frontend=ghcr.io/kulunchick/diploma-frontend:<known-good-sha8>

# Remember: Argo CD will revert this on next sync unless you also
# update values.yaml or pause auto-sync.
```

---

## Force Rebuild Without Code Changes

To push a new image without changing application code (e.g., to pick up a base
image security patch or rebuild Rust after a Cargo.lock update):

```bash
# Touch a file in the component's path to trigger the path filter
git commit --allow-empty -m "chore(cd): force rebuild frontend [skip ci in ci.yml]"

# Or trigger only specific components:
echo "# rebuild trigger $(date)" >> apps/ui/.rebuild
git add apps/ui/.rebuild
git commit -m "chore(cd): force rebuild frontend"
git push origin main
# ci.yml and cd.yml detect the apps/ui/** change and rebuild frontend only.
```

> `[skip ci]` must NOT be in the commit message here — you want CI and CD
> to run.  Add it only to write-back commits to prevent infinite loops.

---

## Ingress WebSocket Notes

Long-running WebSocket connections (`/api/jobs/{id}/events`) are kept alive
by the timeout annotations in `deploy/charts/frontend/values.yaml`:

```yaml
ingress:
  proxyReadTimeout: "3600"
  proxySendTimeout: "3600"
```

These are set to 1 hour.  Experiments that run longer than 1 hour will need
these values increased.

---

## Teardown

```bash
helm uninstall frontend backend worker

# ClusterIssuer is cluster-scoped — delete manually if no longer needed:
kubectl delete -f deploy/cluster-issuer.yaml
```
