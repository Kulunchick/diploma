#!/usr/bin/env python3
"""Reproducible demo dataset for the service-package formation system.

Seeds a fixed demo account (``demo@demo.com`` / ``demo12345``) with a 50-service
× 10-provider catalogue grouped into 10 all-or-nothing service packages
(logical units), and fills all FIVE planning matrices for every cell:

    price d_ij · resource β_ij · provider_revenue p_ij · discount r_ij · min_value s_ij

The instance is built so that:

  * **Relative value > 0.9 with room.** The relative value of a (service,
    provider) cell is the quantity constraint (4) thresholds against s_ij — the
    UI calls s_ij "Мін. відносна цінність" (minimum relative value):

        RV = p_ij / ((1 − r_ij) · d_ij)          (constraint (4): s ≤ RV ⇔ s·(1−r)·d ≤ p)

    Every seeded cell has RV well above 1 (min ≈ 1.3), so all cells are
    admissible under constraint (4) with comfortable room to spare (RV ≫ s).
    We also report the greedy heuristic θ = d·(1−r)/β (common.rs::heuristic).

  * **Binding resource constraint.** Σ of all unit×provider resources greatly
    exceeds the chosen total resource T, so not everything fits and the methods
    must CHOOSE — constraint (3) ΣΣ β·v ≤ T binds. This makes the optimisation
    meaningful and the convergence chart non-trivial.

  * **A clear combined-method advantage.** Mild price (d) anti-correlation with
    strong provider-revenue (p) variation: the F_IT-maximising probabilistic /
    ant-colony methods chase IT-favourable (high d/β) units, while the combined
    method's Pareto local search also grabs the provider-favourable (high p)
    units AND lowers discounts toward 0 (a pure Pareto step that lifts F_IT
    without touching F_prov). Result: combined wins F_IT, F_prov and total
    benefit. See docs/combined-method.md.

Deterministic & idempotent: a fixed RNG seed yields the SAME dataset every run;
services/providers are reused by name (stable ids), groups + formations are
reset, planning cells are upserted — re-running never duplicates.

Seeds through the public API (goes through the same Pydantic / DB validation the
UI uses). Zero third-party dependencies — plain ``python scripts/seed_demo.py``.

Target environment (default): the live cluster at https://mkrasovs.xyz
(override with --base or SEED_API_BASE). This is the user's own single-tenant
demo instance.

Usage:
    python scripts/seed_demo.py                 # seed + verify (idempotent)
    python scripts/seed_demo.py --run-methods   # also run all 3 methods + compare
    python scripts/seed_demo.py --verify-only    # generate + verify locally, no API writes
    python scripts/seed_demo.py --base http://localhost:8000
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Windows consoles default to cp1252 and choke on the Cyrillic / math glyphs
# (β, θ, −) in our output. Force UTF-8 so the script prints cleanly everywhere.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE = os.getenv("SEED_API_BASE", "https://mkrasovs.xyz")
EMAIL = "demo@demo.com"          # EmailStr-valid (single-label "demo@demo" is rejected)
PASSWORD = "demo12345"           # ≥6 chars — matches UserCreate(password: min_length=6)
FULL_NAME = "Демонстраційний користувач"

SEED = 20260613                  # fixed → identical dataset every run

N_PROVIDERS = 10
N_SERVICES = 50
GROUP_SIZE = 5                   # 50 services / 5 = 10 all-or-nothing packages (units)

# Binding fraction: T = round(BIND_FRACTION · Σ all unit×provider resource).
# 0.5 ⇒ at most ~half of all assignments fit by resource → the methods must choose.
BIND_FRACTION = 0.50

# --- per-cell number generation (see module docstring for the rationale) ----
D_HI, D_LO = 1250, 950           # IT preferential price d: mild anti-correlation
P_LO, P_HI = 1200, 2400          # provider revenue p: strong variation (drives F_prov)
R_BASE = 0.30                    # planning discount r0 (combined lowers it → F_IT lift)
S_BASE = 0.50                    # min relative value s (≪ RV ⇒ admissible with room)

RV_FLOOR = 0.9                   # hard assertion threshold from the task
RV_TARGET = 1.2                  # comfortable-margin target we actually design for

# 10 thematic packages of 5 services each (the all-or-nothing units).
PACKAGES: list[tuple[str, list[str]]] = [
    ("Хостинг та інфраструктура",
     ["Віртуальний хостинг", "VPS", "Виділений сервер", "Колокація", "Хмара IaaS"]),
    ("Мережа та зв'язність",
     ["DNS-хостинг", "IP-транзит", "Пірінг", "BGP-маршрутизація", "Резервний канал"]),
    ("Уніфіковані комунікації",
     ["VoIP-телефонія", "SIP-транкінг", "Відеоконференції", "Корпоративний месенджер", "Контакт-центр"]),
    ("Кібербезпека",
     ["Захист від DDoS", "Міжмережевий екран", "VPN-доступ", "SSL-сертифікати", "SOC-моніторинг"]),
    ("Зберігання даних",
     ["Об'єктне сховище", "Резервне копіювання", "Файловий сервіс", "Архівне сховище", "Синхронізація даних"]),
    ("Доставка контенту",
     ["CDN", "Відеостримінг", "Кешування", "Транскодування медіа", "Веб-прискорення"]),
    ("Бізнес-платформи",
     ["CRM (SaaS)", "ERP-система", "Поштовий сервіс", "Корпоративний портал", "BI-платформа"]),
    ("Хмарні обчислення",
     ["GPU-обчислення", "Kubernetes-платформа", "FaaS-функції", "Черги повідомлень", "Балансувальник"]),
    ("Дані та аналітика",
     ["Кероване СУБД", "Сховище даних (DWH)", "Потокова аналітика", "Озеро даних", "ETL-сервіс"]),
    ("Підтримка та сервіс",
     ["Техпідтримка 24/7", "Керований моніторинг", "ІТ-консалтинг", "Міграція в хмару", "Навчання"]),
]

PROVIDERS: list[str] = [
    "Київстар", "Vodafone Україна", "lifecell", "Datagroup", "Укртелеком",
    "Volia", "Triolan", "Ланет", "Інтертелеком", "Фрегат",
]

# Per-category resource base β (decoupled from d/p so θ = d(1−r)/β varies → the
# probabilistic/ant methods have genuine preferences and skip some high-p units).
BETA_BASE = [70, 150, 90, 110, 160, 130, 100, 180, 140, 80]


# ---------------------------------------------------------------------------
# Dataset generation (pure, deterministic)
# ---------------------------------------------------------------------------

class Cell:
    __slots__ = ("si", "pj", "d", "beta", "p", "r", "s")

    def __init__(self, si: int, pj: int, d: int, beta: int, p: int, r: float, s: float):
        self.si, self.pj = si, pj
        self.d, self.beta, self.p, self.r, self.s = d, beta, p, r, s

    def rv(self) -> float:
        """Relative value p / ((1−r)·d) — what constraint (4) compares to s."""
        return self.p / ((1.0 - self.r) * self.d)

    def theta(self) -> float:
        """Greedy heuristic θ = d·(1−r)/β (common.rs::heuristic)."""
        return self.d * (1.0 - self.r) / self.beta

    def admissible(self) -> bool:
        """Constraint (4): s·(1−r)·d ≤ p (common.rs::is_admissible)."""
        return self.s * (1.0 - self.r) * self.d <= self.p


def _profile(group_index: int) -> float:
    """Group profile t ∈ [0,1]: 0 = IT-favourable, 1 = provider-favourable."""
    n_groups = N_SERVICES // GROUP_SIZE
    return group_index / (n_groups - 1)


def generate() -> tuple[list[Cell], int]:
    """Build all N_SERVICES×N_PROVIDERS cells and the total resource T.

    Integers for d, β, p (the solver truncates price/resource to int at the unit
    boundary — using ints means our computed metrics match the solver exactly).
    r, s are 4-decimal floats (NUMERIC(6,4) / NUMERIC(8,4)).
    """
    rng = random.Random(SEED)
    cells: list[Cell] = []
    for si in range(N_SERVICES):
        g = si // GROUP_SIZE
        t = _profile(g)
        beta_base = BETA_BASE[g]
        for pj in range(N_PROVIDERS):
            # Provider attractiveness multiplier (cancels in RV: appears in both d & p).
            a = 1.0 + (pj - (N_PROVIDERS - 1) / 2) * 0.03
            a_beta = 1.0 + (pj - (N_PROVIDERS - 1) / 2) * 0.025
            jd = rng.uniform(0.96, 1.04)
            jp = rng.uniform(0.96, 1.04)
            jb = rng.uniform(0.90, 1.10)

            d = round((D_HI - (D_HI - D_LO) * t) * a * jd)
            p = round((P_LO + (P_HI - P_LO) * t) * a * jp)
            beta = round(beta_base * a_beta * jb)

            r = R_BASE + (pj - (N_PROVIDERS - 1) / 2) * 0.012 + rng.uniform(-0.03, 0.03)
            r = round(min(0.45, max(0.10, r)), 4)
            s = round(min(0.70, max(0.20, S_BASE + rng.uniform(-0.05, 0.05))), 4)

            cells.append(Cell(si, pj, int(d), int(beta), int(p), r, s))

    total_resource = sum(c.beta for c in cells)
    t_total = round(BIND_FRACTION * total_resource)
    return cells, t_total


# ---------------------------------------------------------------------------
# Local verification (pure — needs no API/stack)
# ---------------------------------------------------------------------------

def _unit_aggregate(cells: list[Cell]) -> dict[tuple[int, int], dict]:
    """Aggregate cells into unit×provider rows the way the API does
    (formations.py::_build_payload): c=Σd, β=Σβ, p=Σp, s=max(s),
    r = price-weighted Σ(r·d)/Σd."""
    by_pair = {(c.si, c.pj): c for c in cells}
    units = {}  # unit index g -> list of service indices
    for si in range(N_SERVICES):
        units.setdefault(si // GROUP_SIZE, []).append(si)

    agg: dict[tuple[int, int], dict] = {}
    for g, members in units.items():
        for pj in range(N_PROVIDERS):
            c_sum = sum(by_pair[(si, pj)].d for si in members)
            b_sum = sum(by_pair[(si, pj)].beta for si in members)
            p_sum = sum(by_pair[(si, pj)].p for si in members)
            s_max = max(by_pair[(si, pj)].s for si in members)
            dw = sum(by_pair[(si, pj)].r * by_pair[(si, pj)].d for si in members)
            r_unit = dw / c_sum if c_sum else 0.0
            rv = p_sum / ((1.0 - r_unit) * c_sum) if c_sum else 0.0
            agg[(g, pj)] = dict(c=c_sum, b=b_sum, p=p_sum, s=s_max, r=r_unit, rv=rv,
                                admissible=s_max * (1.0 - r_unit) * c_sum <= p_sum)
    return agg


def verify(cells: list[Cell], t_total: int) -> None:
    """Assert RV>0.9 (cell + unit level), admissibility with room, and a binding
    T. Print sample cells + summary. Raises AssertionError on any violation."""
    print("\n" + "=" * 72)
    print("VERIFICATION (computed from the seeded numbers — no stack needed)")
    print("=" * 72)

    # --- cell level ---------------------------------------------------------
    rvs = [c.rv() for c in cells]
    thetas = [c.theta() for c in cells]
    margins = [c.rv() - c.s for c in cells]   # room to spare on constraint (4)
    min_rv = min(rvs)
    n_inadmissible = sum(0 if c.admissible() else 1 for c in cells)

    print(f"\nPer-cell relative value  RV = p / ((1−r)·d):")
    print(f"    cells               : {len(cells)}  (50 services × 10 providers)")
    print(f"    RV  min / mean / max: {min_rv:.3f} / {sum(rvs)/len(rvs):.3f} / {max(rvs):.3f}")
    print(f"    θ   min / mean / max: {min(thetas):.2f} / {sum(thetas)/len(thetas):.2f} / {max(thetas):.2f}")
    print(f"    room (RV − s) min   : {min(margins):.3f}")
    print(f"    inadmissible cells  : {n_inadmissible}")

    print("\n    sample cells (service, provider) →  d    β    p     r      s     RV     θ:")
    sample_idx = [0, 7, 95, 222, 333, 410, 499]  # spread across the spectrum
    for idx in sample_idx:
        c = cells[idx]
        gname = PACKAGES[c.si // GROUP_SIZE][0][:22]
        print(f"      s{c.si:02d}/{gname:<22} p{c.pj:02d}  "
              f"{c.d:>5} {c.beta:>4} {c.p:>5} {c.r:>5.3f} {c.s:>5.3f} {c.rv():>5.2f} {c.theta():>6.2f}")

    assert min_rv > RV_FLOOR, f"min cell RV {min_rv:.3f} ≤ {RV_FLOOR}"
    assert n_inadmissible == 0, f"{n_inadmissible} inadmissible cells"
    assert min(margins) > 0.2, f"thin room to spare: {min(margins):.3f}"
    print(f"\n    ✓ every cell RV > {RV_FLOOR} (min {min_rv:.3f}); all admissible with room ≥ {min(margins):.2f}")

    # --- unit (aggregated) level — what the solver actually evaluates --------
    agg = _unit_aggregate(cells)
    urvs = [v["rv"] for v in agg.values()]
    u_inadm = sum(0 if v["admissible"] else 1 for v in agg.values())
    assert min(urvs) > RV_FLOOR, f"min unit RV {min(urvs):.3f} ≤ {RV_FLOOR}"
    assert u_inadm == 0
    print(f"    ✓ unit×provider RV (aggregated, 10×10): min {min(urvs):.3f} > {RV_FLOOR}; all admissible")

    # --- binding resource constraint ---------------------------------------
    total_resource = sum(c.beta for c in cells)
    # Cheapest single assignment of every unit to its lowest-β provider:
    min_assign = 0
    for g in range(N_SERVICES // GROUP_SIZE):
        min_assign += min(agg[(g, pj)]["b"] for pj in range(N_PROVIDERS))
    print(f"\nBinding resource constraint (3)  ΣΣ β·v ≤ T:")
    print(f"    Σ all unit×provider resource : {total_resource:>8}")
    print(f"    chosen total resource T      : {t_total:>8}   (= {BIND_FRACTION:.0%} of the above)")
    print(f"    T / total                    : {t_total/total_resource:>8.1%}")
    print(f"    min resource to give every unit one provider: {min_assign}")
    assert total_resource > t_total, "T does not bind"
    assert t_total > min_assign, "T too small — not even one provider per unit fits"
    print(f"    ✓ T binds: only ~{t_total/total_resource:.0%} of all assignments fit by resource "
          f"→ the methods must choose")
    print("=" * 72)


# ---------------------------------------------------------------------------
# HTTP client (stdlib urllib)
# ---------------------------------------------------------------------------

class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.token: str | None = None

    # A real browser User-Agent — the live site sits behind Cloudflare, whose
    # WAF bans the default "Python-urllib/x.y" signature (error 1010).
    _UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

    def _req(self, method: str, path: str, *, json_body=None, form=None,
             auth=True, ok=(200, 201)) -> tuple[int, object]:
        url = f"{self.base}{path}"
        headers = {"Accept": "application/json", "User-Agent": self._UA,
                   "Accept-Language": "uk,en;q=0.9"}
        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
        elif form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    body = resp.read().decode() or "null"
                    return resp.status, json.loads(body)
            except urllib.error.HTTPError as e:
                body = e.read().decode()
                try:
                    parsed = json.loads(body)
                except ValueError:
                    parsed = body
                if e.code not in ok and e.code >= 500 and attempt < 3:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return e.code, parsed
            except urllib.error.URLError as e:
                if attempt < 3:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise SystemExit(f"network error reaching {url}: {e}")
        raise SystemExit(f"failed: {method} {url}")

    def get(self, path):
        return self._req("GET", path)

    def post(self, path, json_body=None, ok=(200, 201)):
        return self._req("POST", path, json_body=json_body, ok=ok)

    def delete(self, path):
        return self._req("DELETE", path, ok=(200, 204))


# ---------------------------------------------------------------------------
# API seeding (idempotent)
# ---------------------------------------------------------------------------

def authenticate(api: Api) -> None:
    code, body = api.post("/api/auth/register",
                          json_body={"email": EMAIL, "password": PASSWORD, "full_name": FULL_NAME},
                          ok=(201, 409))
    if code not in (201, 409):
        raise SystemExit(f"register failed: {code} {body}")
    # login uses an OAuth2 password *form*, not JSON:
    code, body = api._req("POST", "/api/auth/login",
                          form={"username": EMAIL, "password": PASSWORD}, auth=False, ok=(200,))
    if code != 200:
        raise SystemExit(f"login failed: {code} {body}")
    api.token = body["access_token"]
    print(f"  authenticated as {EMAIL}")


def reset_and_seed(api: Api, cells: list[Cell]) -> dict:
    """Idempotently bring the demo user's catalogue to the exact target state."""
    target_services = [name for _, names in PACKAGES for name in names]
    target_providers = list(PROVIDERS)

    # 1) wipe prior formations (clean slate for the live demo runs)
    _, formations = api.get("/api/formations")
    for f in formations or []:
        api.delete(f"/api/formations/{f['id']}")
    if formations:
        print(f"  cleared {len(formations)} prior formation scenario(s)")

    # 2) reset groups (so memberships can be re-created without unique conflicts)
    _, groups = api.get("/api/service-groups")
    for grp in groups or []:
        api.delete(f"/api/service-groups/{grp['id']}")

    # 3) reconcile providers (ensure target, drop strays) — stable ids
    _, existing = api.get("/api/providers")
    prov_id = {p["name"]: p["id"] for p in (existing or [])}
    for name in target_providers:
        if name not in prov_id:
            _, b = api.post("/api/providers",
                            {"name": name, "description": f"Провайдер інфокомунікацій «{name}»"})
            prov_id[name] = b["id"]
    for p in (existing or []):
        if p["name"] not in target_providers:
            api.delete(f"/api/providers/{p['id']}")

    # 4) reconcile services (ensure target, drop strays) — stable ids
    _, existing = api.get("/api/services")
    svc_id = {s["name"]: s["id"] for s in (existing or [])}
    for gi, (gname, names) in enumerate(PACKAGES):
        for name in names:
            if name not in svc_id:
                _, b = api.post("/api/services",
                                {"name": name, "description": f"Сервіс «{name}» (пакет «{gname}»)"})
                svc_id[name] = b["id"]
    for s in (existing or []):
        if s["name"] not in target_services:
            api.delete(f"/api/services/{s['id']}")

    # 5) (re)create the 10 all-or-nothing packages
    for gname, names in PACKAGES:
        _, b = api.post("/api/service-groups",
                        {"name": gname, "member_ids": [svc_id[n] for n in names]}, ok=(201, 409))
    print(f"  catalogue: {len(svc_id)} services, {len(prov_id)} providers, {len(PACKAGES)} packages")

    # 6) bulk-upsert all 500 planning cells in one request (idempotent)
    svc_by_index = [svc_id[name] for _, names in PACKAGES for name in names]
    prov_by_index = [prov_id[name] for name in PROVIDERS]
    payload = [{
        "service_id": svc_by_index[c.si],
        "provider_id": prov_by_index[c.pj],
        "price": c.d, "resource": c.beta, "provider_revenue": c.p,
        "discount": c.r, "min_value": c.s,
    } for c in cells]
    code, body = api.post("/api/planning/bulk", {"cells": payload}, ok=(200,))
    if code != 200:
        raise SystemExit(f"planning bulk failed: {code} {body}")
    print(f"  planning: upserted {len(payload)} cells (server now holds {len(body)})")

    return {"service_ids": svc_by_index, "provider_ids": prov_by_index,
            "returned_cells": body}


def verify_roundtrip(cells: list[Cell], returned: list[dict]) -> None:
    """Confirm the server stored exactly what we sent (round-trip through the
    same validation the UI uses), and re-assert RV>0.9 on the stored data."""
    by_pair = {(r["service_id"], r["provider_id"]): r for r in returned}
    assert len(returned) >= len(cells), f"server returned {len(returned)} < {len(cells)} cells"
    min_rv = float("inf")
    for r in returned:
        d, p, disc = float(r["price"]), float(r["provider_revenue"]), float(r["discount"])
        if d > 0:
            min_rv = min(min_rv, p / ((1.0 - disc) * d))
    assert min_rv > RV_FLOOR, f"server-stored min RV {min_rv:.3f} ≤ {RV_FLOOR}"
    print(f"  ✓ round-trip OK: server-stored cells all have RV > {RV_FLOOR} (min {min_rv:.3f})")


# ---------------------------------------------------------------------------
# Optional: run all three methods + compare (proves the combined advantage)
# ---------------------------------------------------------------------------

def run_methods(api: Api, t_total: int) -> None:
    def run(name: str, algorithm: str, params: dict) -> dict:
        code, b = api.post("/api/formations",
                           {"name": name, "b_total": t_total, "algorithm": algorithm, "params": params},
                           ok=(201,))
        if code != 201:
            raise SystemExit(f"create formation failed: {code} {b}")
        sid = b["id"]
        for _ in range(240):
            time.sleep(1)
            _, d = api.get(f"/api/formations/{sid}")
            if d.get("status") in ("completed", "failed"):
                _, it = api.get(f"/api/formations/{sid}/iterations")
                d["_iters"] = len(it or [])
                return d
        return {"status": "timeout"}

    print("\n" + "=" * 72)
    print(f"RUNNING ALL THREE METHODS  (T = {t_total})")
    print("=" * 72)
    a = run("Демо — ймовірнісно-жадібний", "probabilistic", {"Kmax": 600})
    b = run("Демо — мурашині колонії", "ant_colony",
            {"Kmax": 300, "num_ants": 25, "alpha": 1, "beta": 3, "p": 0.1, "tau": 1})
    cm = run("Демо — комбінований метод", "combined",
             {"kmax_subproblem": 300, "discount_step": 0.05,
              "ignore_discounts": False, "local_search_restarts": 4})

    print(f"\n{'метод':<26}{'F_IT':>10}{'F_prov':>11}{'вигода':>11}{'iter':>6}")
    print("-" * 64)
    rows = [("А ймовірнісно-жадібний", a), ("Б мурашині колонії", b), ("В комбінований", cm)]
    for tag, d in rows:
        if d.get("status") != "completed":
            print(f"{tag:<26}  {d.get('status')}  {d.get('error','')}")
            continue
        fit = float(d["value"] or 0)
        fprov = float(d["provider_value"] or 0)
        print(f"{tag:<26}{fit:>10.0f}{fprov:>11.0f}{fit+fprov:>11.0f}{d.get('_iters',0):>6}"
              + (f"  src={d.get('combined_source')}" if d["algorithm"] == "combined" else ""))

    if cm.get("status") == "completed" and a.get("status") == "completed":
        base = max(float(a["value"] or 0) + float(a["provider_value"] or 0),
                   float(b["value"] or 0) + float(b["provider_value"] or 0))
        combo = float(cm["value"] or 0) + float(cm["provider_value"] or 0)
        print(f"\n  combined total benefit {combo:.0f} vs best single {base:.0f} "
              f"→ {(combo/base - 1)*100:+.1f}%")
    print("=" * 72)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Seed the demo dataset.")
    ap.add_argument("--base", default=DEFAULT_BASE, help="API base URL (default: %(default)s)")
    ap.add_argument("--verify-only", action="store_true",
                    help="generate + verify locally, do NOT touch the API")
    ap.add_argument("--run-methods", action="store_true",
                    help="after seeding, run all three methods and print the comparison")
    args = ap.parse_args()

    print("=" * 72)
    print("SERVICE-PACKAGE FORMATION — DEMO SEED")
    print("=" * 72)
    print(f"  target API : {args.base}")
    print(f"  dataset    : {N_SERVICES} services / {N_PROVIDERS} providers / "
          f"{len(PACKAGES)} packages (units)")
    print(f"  RNG seed   : {SEED} (deterministic)")

    cells, t_total = generate()
    verify(cells, t_total)

    if args.verify_only:
        print("\n--verify-only: skipping API writes.")
        print(f"\nDEMO LOGIN  →  {EMAIL}  /  {PASSWORD}")
        return

    print("\n" + "=" * 72)
    print(f"SEEDING via {args.base}")
    print("=" * 72)
    api = Api(args.base)
    authenticate(api)
    result = reset_and_seed(api, cells)
    verify_roundtrip(cells, result["returned_cells"])

    if args.run_methods:
        run_methods(api, t_total)

    print("\n" + "=" * 72)
    print(f"DONE.  DEMO LOGIN  →  {EMAIL}  /  {PASSWORD}")
    print(f"       {args.base}")
    print("=" * 72)


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"\nVERIFICATION FAILED: {e}", file=sys.stderr)
        sys.exit(1)
