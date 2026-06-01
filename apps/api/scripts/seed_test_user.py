"""Seed a test user with an ANTI-CORRELATED instance and run all three
algorithms, printing the A-vs-B-vs-combined comparison + invariant checks.

The instance is deliberately anti-correlated: IT-favorable services have high
preferential price d but low provider revenue p; provider-favorable services
have low d but high p. s_ij (min relative value) is non-trivial so constraint
(4) can bind and the combined method's discount-concession lever matters.

Run (stack must be up):  uv run python scripts/seed_test_user.py
"""
import time

import httpx

BASE = "http://localhost:8000"
EMAIL = "test@example.com"
PASSWORD = "test12345"

# service -> (d_base IT price, p_base provider revenue). Anti-correlated:
# d decreasing, p increasing down the list. resource (beta) uniform.
SERVICE_BASES: dict[str, tuple[int, int]] = {
    "Хостинг": (1000, 200),         # IT-favorable  ┐ group "Базовий пакет"
    "DNS-сервіс": (900, 250),       # IT-favorable  ┘
    "VPN-доступ": (600, 600),       # balanced      ┐ group "Преміум зв'язок"
    "CDN": (550, 650),              # balanced      ┘
    "Поштовий сервіс": (300, 950),  # provider-favorable
    "Хмарне сховище": (250, 1000),  # provider-favorable
}
B_RESOURCE = 500
R_MAX = 0.20
S_MIN = 0.45

GROUPS = {
    "Базовий пакет": ["Хостинг", "DNS-сервіс"],
    "Преміум зв'язок": ["VPN-доступ", "CDN"],
}
PROVIDERS = ["Київстар", "Vodafone", "Lifecell", "Datagroup"]


def main() -> None:
    c = httpx.Client(base_url=BASE, timeout=60)

    r = c.post("/api/auth/register",
               json={"email": EMAIL, "password": PASSWORD, "full_name": "Тестовий користувач"})
    if r.status_code not in (200, 201, 409):
        raise SystemExit(f"register failed: {r.status_code} {r.text}")
    tok = c.post("/api/auth/login", data={"username": EMAIL, "password": PASSWORD}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    print(f"user ready: {EMAIL} / {PASSWORD}")

    def ensure(kind: str, name: str, extra: dict) -> str:
        existing = {x["name"]: x["id"] for x in c.get(f"/api/{kind}", headers=h).json()}
        if name in existing:
            return existing[name]
        return c.post(f"/api/{kind}", json={"name": name, **extra}, headers=h).json()["id"]

    svc = {n: ensure("services", n, {"description": f"Сервіс «{n}»"}) for n in SERVICE_BASES}
    prov = {n: ensure("providers", n, {"description": f"Провайдер «{n}»"}) for n in PROVIDERS}
    existing_groups = {g["name"] for g in c.get("/api/service-groups", headers=h).json()}
    for gname, members in GROUPS.items():
        if gname not in existing_groups:
            c.post("/api/service-groups",
                   json={"name": gname, "member_ids": [svc[m] for m in members]}, headers=h)
    print(f"services: {len(svc)}, providers: {len(prov)}, groups: {len(GROUPS)}")

    prov_ids_sorted = [prov[n] for n in sorted(prov)]
    cells = []
    for name, (d_base, p_base) in SERVICE_BASES.items():
        for j, pid in enumerate(prov_ids_sorted):
            cells.append({
                "service_id": svc[name], "provider_id": pid,
                "price": d_base + 30 * j, "resource": B_RESOURCE,
                "provider_revenue": p_base + 40 * j,
                "discount": R_MAX, "min_value": S_MIN,
            })
    c.post("/api/planning/bulk", json={"cells": cells}, headers=h)
    b_total = int(len(cells) * B_RESOURCE * 0.5)
    print(f"planning cells: {len(cells)}, b_total: {b_total}")

    # clear prior scenarios so the comparison stays clean
    for f in c.get("/api/formations", headers=h).json():
        c.delete(f"/api/formations/{f['id']}", headers=h)

    p_by_pair = {(x["service_id"], x["provider_id"]): x["provider_revenue"] for x in cells}

    def run(name: str, algorithm: str, params: dict) -> dict:
        sid = c.post("/api/formations",
                     json={"name": name, "b_total": b_total, "algorithm": algorithm, "params": params},
                     headers=h).json()["id"]
        for _ in range(180):
            time.sleep(1)
            d = c.get(f"/api/formations/{sid}", headers=h).json()
            if d["status"] in ("completed", "failed"):
                return d
        return {"status": "timeout"}

    a = run("Сценарій А — ймовірнісно-жадібний", "probabilistic", {"Kmax": 500})
    b = run("Сценарій Б — мурашиних колоній", "ant_colony",
            {"Kmax": 300, "num_ants": 25, "alpha": 1, "beta": 3, "p": 0.1, "tau": 1})
    cm = run("Сценарій В — комбінований метод", "combined",
             {"kmax_subproblem": 300, "discount_step": 0.05, "ignore_discounts": False,
              "local_search_restarts": 3})

    def f_prov_of(detail: dict) -> float:
        total = 0.0
        for asg in detail.get("assignments", []):
            p = p_by_pair.get((asg["service_id"], asg["provider_id"]), 0)
            rr = asg.get("final_discount")
            if rr is None:
                rr = asg["discount"]
            total += (1.0 - rr) * p
        return total

    print("\n================ A vs B vs Combined ================")
    for tag, d in [("А (ймов.-жадібн.)", a), ("Б (мурашиних)", b), ("В (комбінований)", cm)]:
        if d["status"] != "completed":
            print(f"{tag}: {d['status']} ERROR={d.get('error')}")
            continue
        fit = d["value"]
        fpr = d["provider_value"] if d.get("provider_value") is not None else f_prov_of(d)
        print(f"{tag:22} F_IT={fit:10.1f}  F_prov={fpr:10.1f}  benefit={fit + fpr:10.1f}"
              + (f"  src={d.get('combined_source')}" if d["algorithm"] == "combined" else ""))

    if cm["status"] == "completed":
        seff = sum(x["effective_revenue"] for x in cm["assignments"])
        negotiated = [x for x in cm["assignments"]
                      if x["final_discount"] is not None and abs(x["final_discount"] - x["discount"]) > 1e-9]
        print(f"\nΣ effective_revenue={seff:.2f} vs F_IT={cm['value']:.2f} (Δ={abs(seff - cm['value']):.2e})")
        print(f"assignments with negotiated discount ≠ r_max: {len(negotiated)}/{len(cm['assignments'])}")

    print(f"\nDONE — login: {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    main()
