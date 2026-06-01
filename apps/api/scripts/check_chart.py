"""Verify the combined scenario's persisted iteration history is monotonic,
contiguous on X, and ends at the stored combined benefit."""
import httpx

c = httpx.Client(base_url="http://localhost:8000", timeout=30)
tok = c.post("/api/auth/login", data={"username": "test@example.com", "password": "test12345"}).json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}

combined = next(f for f in c.get("/api/formations", headers=h).json() if f["algorithm"] == "combined")
d = c.get(f"/api/formations/{combined['id']}", headers=h).json()
benefit = d["value"] + d["provider_value"]

its = c.get(f"/api/formations/{combined['id']}/iterations", headers=h).json()
xs = [p["iteration"] for p in its]
ys = [p["best_value"] for p in its]

mono = all(ys[i] <= ys[i + 1] + 1e-9 for i in range(len(ys) - 1))
contiguous = xs == list(range(xs[0], xs[0] + len(xs)))
print(f"points={len(its)}  x=[{xs[0]}..{xs[-1]}]  contiguous={contiguous}")
print(f"monotonic={mono}  first_y={ys[0]:.0f}  last_y={ys[-1]:.0f}  max_y={max(ys):.0f}")
print(f"combined_benefit(cards)={benefit:.0f}")
print(f"last==benefit: {abs(ys[-1]-benefit)<1e-6}   max==benefit: {abs(max(ys)-benefit)<1e-6}")
drops = [(xs[i], ys[i], ys[i+1]) for i in range(len(ys)-1) if ys[i+1] < ys[i] - 1e-9]
print(f"mid-chart drops: {len(drops)}  {drops[:3]}")
