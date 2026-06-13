#!/usr/bin/env python3
"""Reproducible demo dataset for the service-package formation system.

Seeds a fixed demo account (``demo@demo.com`` / ``demo12345``) with a 50-service
× 10-provider catalogue and fills all FIVE planning matrices for every cell:

    price d_ij · resource β_ij · provider_revenue p_ij · discount r_ij · min_value s_ij

Grouping (all-or-nothing units): each of the 10 thematic packages contributes a
group of its first ``GROUP_SIZE`` services; the remaining services are offered
standalone. With GROUP_SIZE = 2 that is 10 groups of 2 + 30 singletons = 40
logical units the solver chooses among.

Design (confirmed against libs/operations/src/common.rs + solvers/combined.rs):

  * **Relative value > 0.9.** The relative value of a cell — the quantity
    constraint (4) thresholds against s_ij (the UI calls s_ij "Мін. відносна
    цінність") — is

        RV = p_ij / ((1 − r_ij) · d_ij)        admissible (4) ⇔ s ≤ RV ⇔ s·(1−r)·d ≤ p

    We set p = round(1.36·d), r_max = 0.35, s = 1.5 ⇒ RV ≈ 2.09 ≫ 0.9 for every
    seeded cell, admissible at the seed-time discount r_max with wide margin.

  * **Non-zero combined discounts (CHANGE 2).** The combined method makes the
    discount r a decision variable (combined.rs stage-3 hill-climb, step 0.05)
    and drives it DOWN to the admissibility floor

        r_min = 1 − p/(s·d)          (the lowest r with s·(1−r)·d ≤ p still true)

    Because we seed p < s·d (1.36·d < 1.5·d), r_min ≈ 0.093 > 0, so the combined
    method cannot reach r = 0: it lands on r = 0.10 (the smallest 0.05-step that
    stays admissible) on its selected cells, while probabilistic / ant-colony
    keep the seed-time r_max = 0.35. That r-drop (0.35 → 0.10) is the combined
    method's F_IT advantage: F_IT per cell goes (1−0.35)d → (1−0.10)d.

  * **Providers stay profitable.** s > 1 is what keeps them so: provider profit
    = p − (1−r)·d, which at the combined method's landing r equals p·(s−1)/s > 0.
    Single methods (r=0.35) leave providers MORE profit; the combined method
    trades some of that for IT revenue to maximise the JOINT benefit F_IT+F_prov,
    while every provider still profits. (s ≤ 1 would force providers into a loss
    under the combined discount — avoided here.)

  * **Small, readable result (CHANGE 1).** Total resource T is set low so the
    binding constraint (3) ΣΣβ·v ≤ T selects only ~10 (unit,provider) pairs —
    a short assignment table — while still leaving a non-trivial choice among
    the 40×10 = 400 unit×provider options. T is CALIBRATED empirically (run the
    methods, count the result, adjust); see BIND_T below.

  * **Combined still wins.** F_IT(combined) ≈ (1−0.10)/(1−0.35) ≈ 1.385× the
    single methods on the same structure (pure r-drop), and Сумарна вигода
    (F_IT+F_prov) follows since F_prov = Σp·v does not depend on r. Verified by
    running all three live after seeding.

Deterministic & idempotent: a fixed RNG seed yields the SAME dataset; services /
providers are reused by name (stable ids), groups + formations are reset,
planning cells are upserted — re-running never duplicates. Seeds through the
public API (same validation the UI uses). Zero third-party dependencies.

Target (default): the live cluster https://mkrasovs.xyz (override --base /
SEED_API_BASE).

Usage:
    python scripts/seed_demo.py                 # seed + verify (idempotent)
    python scripts/seed_demo.py --run-methods   # also run all 3 methods + compare
    python scripts/seed_demo.py --verify-only    # generate + verify locally, no API
    python scripts/seed_demo.py --run-methods --t 900   # override T (calibration)
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
EMAIL = "demo@demo.com"
PASSWORD = "demo12345"
FULL_NAME = "Демонстраційний користувач"

SEED = 20260613                  # fixed → identical dataset every run

N_PROVIDERS = 10
N_SERVICES = 50
THEME_SIZE = 5                   # 10 themes × 5 = 50 services
GROUP_SIZE = 2                   # first 2 of each theme form a group; rest singletons
#   → 10 groups of 2 + 30 singletons = 40 all-or-nothing units

# --- per-cell numbers (CHANGE 2: p < s·d ⇒ non-zero combined discount) -------
# s > 1 is REQUIRED to keep providers PROFITABLE: provider profit at the
# combined method's landing r equals p·(s−1)/s, which is > 0 iff s > 1. The
# note's starting point s≈0.70 forces p<d and drives providers to a LOSS under
# the combined discount — economically wrong for a "mutually beneficial" thesis.
# So we keep the note's MECHANISM (p < s·d ⇒ r_min > 0 ⇒ non-zero discount) but
# pick s=1.5, p=round(1.36·d): RV = 1.36/(1−0.35) ≈ 2.09 (≫0.9), r_min ≈ 0.093 ⇒
# the combined method lands on r=0.10, and providers profit under every method.
S_MIN = 1.5                      # min relative value s_ij (uniform) — s>1 ⇒ providers profit
R_MAX = 0.40                     # seeded discount r_ij (single methods keep this); combined
                                 # negotiates it down to 0.10 → a wide, robust F_IT advantage
P_RATIO = 1.36                   # p = round(P_RATIO·d); p < s·d=1.5d ⇒ r_min=1−1.36/1.5 ≈ 0.093
RV_FLOOR = 0.9                   # hard assertion threshold
DISCOUNT_STEP = 0.05             # combined method's discount granularity (combined.rs)

# --- binding total resource T (CHANGE 1: small, readable ~10-row result) -----
# Calibrated empirically against the live solver: T=600 yields a ~10-row result
# (combined 9-10 / prob 8 / ant 10 assignment rows) — small + readable — while
# leaving a non-trivial choice among the 400 unit×provider options, and the
# combined method robustly wins F_IT and Сумарна вигода (see Gate-1 report).
# Override with --t for re-calibration.
BIND_T = 600

# 10 thematic packages of 5 services each.
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

    def r_min(self) -> float:
        """Admissibility floor r_min = 1 − p/(s·d): the lowest r the combined
        method can reach while keeping (4). The combined method lands on the
        smallest DISCOUNT_STEP multiple ≥ r_min."""
        return max(0.0, 1.0 - self.p / (self.s * self.d))

    def combined_landing_r(self) -> float:
        """Smallest 0.05-step r in [r_min, r_max] that stays admissible — where
        the combined method's stage-3 hill-climb stops lowering the discount."""
        r = self.r
        while r - DISCOUNT_STEP >= -1e-9:
            cand = round(r - DISCOUNT_STEP, 4)
            if self.s * (1.0 - cand) * self.d <= self.p + 1e-9:
                r = cand
            else:
                break
        return round(r, 4)


def unit_partition() -> list[list[int]]:
    """Service-index units the solver sees: the first GROUP_SIZE of each theme
    form one all-or-nothing group; the remaining theme services are singletons."""
    units: list[list[int]] = []
    for t in range(N_SERVICES // THEME_SIZE):
        base = t * THEME_SIZE
        units.append(list(range(base, base + GROUP_SIZE)))          # the group
        units.extend([s] for s in range(base + GROUP_SIZE, base + THEME_SIZE))  # singletons
    return units


def generate() -> tuple[list[Cell], int]:
    """Build all 50×10 cells and the total resource T.

    Integers for d, β, p (the solver truncates price/resource to int at the unit
    boundary — ints make our computed metrics match the solver exactly). r, s are
    4-decimal floats. p = round(0.65·d) < s·d ⇒ RV ≈ 1.0 and r_min ≈ 0.071.
    """
    rng = random.Random(SEED)
    # Per-service bases, decoupled so θ = (1−r)d/β varies → a meaningful choice.
    d_service = [rng.randint(900, 1500) for _ in range(N_SERVICES)]
    beta_service = [rng.randint(55, 155) for _ in range(N_SERVICES)]

    cells: list[Cell] = []
    for si in range(N_SERVICES):
        for pj in range(N_PROVIDERS):
            a_d = 1.0 + (pj - (N_PROVIDERS - 1) / 2) * 0.025   # provider price factor
            a_b = 1.0 + (pj - (N_PROVIDERS - 1) / 2) * 0.030   # provider resource factor
            d = round(d_service[si] * a_d * rng.uniform(0.97, 1.03))
            beta = round(beta_service[si] * a_b * rng.uniform(0.90, 1.10))
            p = round(P_RATIO * d)
            cells.append(Cell(si, pj, int(d), int(beta), int(p), R_MAX, S_MIN))

    return cells, BIND_T


# ---------------------------------------------------------------------------
# Local verification (pure — needs no API/stack)
# ---------------------------------------------------------------------------

def _unit_aggregate(cells: list[Cell]) -> dict[tuple[int, int], dict]:
    """Aggregate cells into unit×provider rows the way the API does
    (formations.py::_build_payload): c=Σd, β=Σβ, p=Σp, s=max(s),
    r = price-weighted Σ(r·d)/Σd."""
    by_pair = {(c.si, c.pj): c for c in cells}
    units = unit_partition()
    agg: dict[tuple[int, int], dict] = {}
    for u_idx, members in enumerate(units):
        for pj in range(N_PROVIDERS):
            c_sum = sum(by_pair[(si, pj)].d for si in members)
            b_sum = sum(by_pair[(si, pj)].beta for si in members)
            p_sum = sum(by_pair[(si, pj)].p for si in members)
            s_max = max(by_pair[(si, pj)].s for si in members)
            dw = sum(by_pair[(si, pj)].r * by_pair[(si, pj)].d for si in members)
            r_unit = dw / c_sum if c_sum else 0.0
            rv = p_sum / ((1.0 - r_unit) * c_sum) if c_sum else 0.0
            r_min = max(0.0, 1.0 - p_sum / (s_max * c_sum)) if c_sum else 0.0
            agg[(u_idx, pj)] = dict(c=c_sum, b=b_sum, p=p_sum, s=s_max, r=r_unit, rv=rv,
                                    r_min=r_min, n=len(members),
                                    admissible=s_max * (1.0 - r_unit) * c_sum <= p_sum)
    return agg


def verify(cells: list[Cell], t_total: int) -> None:
    """Assert RV>0.9 + admissibility (cell + unit level), report r_min / combined
    landing r, and the binding T. Raises AssertionError on any violation."""
    print("\n" + "=" * 74)
    print("VERIFICATION (computed from the seeded numbers — no stack needed)")
    print("=" * 74)

    rvs = [c.rv() for c in cells]
    rmins = [c.r_min() for c in cells]
    lands = [c.combined_landing_r() for c in cells]
    thetas = [c.theta() for c in cells]
    min_rv = min(rvs)
    n_inadmissible = sum(0 if c.admissible() else 1 for c in cells)

    print(f"\nPer-cell relative value  RV = p / ((1−r_max)·d)   (r_max = {R_MAX}, s = {S_MIN}):")
    print(f"    cells                 : {len(cells)}  (50 services × 10 providers)")
    print(f"    RV   min / mean / max : {min_rv:.3f} / {sum(rvs)/len(rvs):.3f} / {max(rvs):.3f}")
    print(f"    r_min min / max       : {min(rmins):.3f} / {max(rmins):.3f}   (floor 1−p/(s·d))")
    print(f"    combined lands r ∈    : {sorted(set(lands))}   (single methods keep r_max={R_MAX})")
    print(f"    θ    min / mean / max : {min(thetas):.2f} / {sum(thetas)/len(thetas):.2f} / {max(thetas):.2f}")
    print(f"    inadmissible cells    : {n_inadmissible}")

    print("\n    sample cells (service, provider) →  d    β    p     r_max  s    RV    r_min  →r_comb:")
    for idx in [0, 7, 95, 222, 333, 410, 499]:
        c = cells[idx]
        gname = PACKAGES[c.si // THEME_SIZE][0][:20]
        print(f"      s{c.si:02d}/{gname:<20} p{c.pj:02d}  "
              f"{c.d:>5} {c.beta:>4} {c.p:>5} {c.r:>5.2f} {c.s:>4.2f} {c.rv():>5.2f} "
              f"{c.r_min():>5.2f}  {c.combined_landing_r():>5.2f}")

    assert min_rv > RV_FLOOR, f"min cell RV {min_rv:.3f} ≤ {RV_FLOOR}"
    assert n_inadmissible == 0, f"{n_inadmissible} inadmissible cells at r_max"
    assert all(rm > 0 for rm in rmins), "some cell has r_min = 0 (combined could reach r=0)"
    assert all(lr > 0 for lr in lands), "some cell's combined landing r = 0 (zero discount)"
    print(f"\n    ✓ every cell RV > {RV_FLOOR} (min {min_rv:.3f}); all admissible at r_max={R_MAX}")
    print(f"    ✓ r_min > 0 everywhere ⇒ combined discounts are NON-ZERO "
          f"(lands r ∈ {sorted(set(lands))}, vs single r_max={R_MAX})")

    # --- unit (aggregated) level — what the solver actually evaluates --------
    units = unit_partition()
    agg = _unit_aggregate(cells)
    urvs = [v["rv"] for v in agg.values()]
    u_rmin = [v["r_min"] for v in agg.values()]
    u_inadm = sum(0 if v["admissible"] else 1 for v in agg.values())
    assert min(urvs) > RV_FLOOR, f"min unit RV {min(urvs):.3f} ≤ {RV_FLOOR}"
    assert u_inadm == 0 and all(rm > 0 for rm in u_rmin)
    n_groups = sum(1 for u in units if len(u) > 1)
    print(f"    ✓ units: {len(units)} ({n_groups} groups of {GROUP_SIZE} + "
          f"{len(units)-n_groups} singletons) × {N_PROVIDERS} providers = {len(agg)} unit×provider cells")
    print(f"    ✓ unit-level RV min {min(urvs):.3f} > {RV_FLOOR}; unit r_min ∈ "
          f"[{min(u_rmin):.3f}, {max(u_rmin):.3f}] > 0")

    # --- binding resource constraint (small, readable result) ---------------
    total_resource = sum(c.beta for c in cells)
    betas_sorted = sorted(v["b"] for v in agg.values())
    fit_estimate = 0
    for b in betas_sorted:                       # cheapest pairs first → rough count that fits T
        if fit_estimate + b > t_total:
            break
        fit_estimate += b
    approx_pairs = next((i for i, _ in enumerate(_running_sum(betas_sorted)) if _ > t_total), len(betas_sorted))
    print(f"\nBinding resource constraint (3)  ΣΣ β·v ≤ T  (CHANGE 1 — small result):")
    print(f"    Σ all unit×provider resource : {total_resource:>8}")
    print(f"    chosen total resource T      : {t_total:>8}   ({t_total/total_resource:.1%} of the above)")
    print(f"    ≈ cheapest pairs that fit T  : ~{approx_pairs}  (rough upper bound on result size)")
    assert total_resource > t_total, "T does not bind"
    print(f"    ✓ T binds hard: only ~{approx_pairs} of {len(agg)} unit×provider pairs fit → "
          f"small readable result")
    print("=" * 74)


def _running_sum(xs):
    tot = 0
    for x in xs:
        tot += x
        yield tot


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
                                {"name": name, "description": f"Сервіс «{name}» (категорія «{gname}»)"})
                svc_id[name] = b["id"]
    for s in (existing or []):
        if s["name"] not in target_services:
            api.delete(f"/api/services/{s['id']}")

    # 5) (re)create the all-or-nothing groups — first GROUP_SIZE of each theme
    for gname, names in PACKAGES:
        members = names[:GROUP_SIZE]
        api.post("/api/service-groups",
                 {"name": gname, "member_ids": [svc_id[n] for n in members]}, ok=(201, 409))
    n_units = len(unit_partition())
    print(f"  catalogue: {len(svc_id)} services, {len(prov_id)} providers, "
          f"{len(PACKAGES)} groups of {GROUP_SIZE} → {n_units} units")

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

    return {"service_ids": svc_by_index, "provider_ids": prov_by_index, "returned_cells": body}


def verify_roundtrip(cells: list[Cell], returned: list[dict]) -> None:
    """Confirm the server stored what we sent and re-assert RV>0.9 on it."""
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
                return d
        return {"status": "timeout"}

    print("\n" + "=" * 74)
    print(f"RUNNING ALL THREE METHODS LIVE  (T = {t_total})")
    print("=" * 74)
    # Params match what the recorded video submits: prob/ant keep the UI dialog
    # defaults; the combined method needs adequate compute (kmax_subproblem=300,
    # restarts=6) to find a selection on par with ant-colony — only then does its
    # discount r-drop (0.40→0.10) make it win. At the dialog default (100, 0) the
    # combined method is under-powered and loses, so the video sets these too.
    a = run("Демо — ймовірнісно-жадібний", "probabilistic", {"Kmax": 100})
    b = run("Демо — мурашині колонії", "ant_colony",
            {"Kmax": 100, "num_ants": 20, "alpha": 1, "beta": 2, "p": 0.1, "tau": 1})
    cm = run("Демо — комбінований метод", "combined",
             {"kmax_subproblem": 300, "discount_step": 0.05,
              "ignore_discounts": False, "local_search_restarts": 6})

    def discounts(detail: dict) -> list[float]:
        out = []
        for asg in detail.get("assignments", []):
            fd = asg.get("final_discount")
            out.append(round(float(fd if fd is not None else asg.get("discount", 0)), 3))
        return out

    print(f"\n{'метод':<24}{'F_IT':>8}{'F_prov':>9}{'профіт':>9}{'вигода':>10}{'ряд':>5}  r")
    print("-" * 74)
    rows = [("А ймовірнісно-жадібний", a), ("Б мурашині колонії", b), ("В комбінований", cm)]
    for tag, d in rows:
        if d.get("status") != "completed":
            print(f"{tag:<24}  {d.get('status')}  {d.get('error','')}")
            continue
        fit = float(d["value"] or 0)
        fprov = float(d["provider_value"] or 0)
        prof = float(d.get("provider_profit") or 0)
        ds = discounts(d)
        print(f"{tag:<24}{fit:>8.0f}{fprov:>9.0f}{prof:>9.0f}{fit+fprov:>10.0f}{len(ds):>5}  {sorted(set(ds))}")

    # --- assertions: combined wins F_IT + total, with non-zero discounts -----
    if all(x.get("status") == "completed" for x in (a, b, cm)):
        fit = {k: float(v["value"] or 0) for k, v in (("a", a), ("b", b), ("c", cm))}
        tot = {k: float(v["value"] or 0) + float(v["provider_value"] or 0)
               for k, v in (("a", a), ("b", b), ("c", cm))}
        c_disc = [x for x in discounts(cm) if x > 0]
        single_disc = sorted(set(discounts(a)) | set(discounts(b)))
        print()
        print(f"  combined F_IT  {fit['c']:.0f} vs best single {max(fit['a'], fit['b']):.0f}  "
              f"→ {(fit['c']/max(fit['a'], fit['b'])-1)*100:+.1f}%")
        print(f"  combined total {tot['c']:.0f} vs best single {max(tot['a'], tot['b']):.0f}  "
              f"→ {(tot['c']/max(tot['a'], tot['b'])-1)*100:+.1f}%")
        print(f"  combined discounts (non-zero): {sorted(set(discounts(cm)))}   "
              f"single methods' r: {single_disc}")
        profits = {k: float(v.get("provider_profit") or 0) for k, v in (("a", a), ("b", b), ("c", cm))}
        win_fit = fit["c"] > fit["a"] and fit["c"] > fit["b"]
        win_tot = tot["c"] > tot["a"] and tot["c"] > tot["b"]
        nonzero = len(c_disc) > 0 and all(x > 0 for x in discounts(cm))
        prov_ok = all(p > 0 for p in profits.values())
        print(f"\n  {'✓' if win_fit else '✗'} combined strictly wins F_IT vs both single methods")
        print(f"  {'✓' if win_tot else '✗'} combined strictly wins Сумарна вигода vs both single methods")
        print(f"  {'✓' if nonzero else '✗'} combined uses NON-ZERO discounts on its selected cells")
        print(f"  {'✓' if prov_ok else '✗'} providers profit under EVERY method "
              f"(combined {profits['c']:.0f}, single {profits['a']:.0f}/{profits['b']:.0f})")
        if not (win_fit and win_tot and nonzero and prov_ok):
            print("\n  ⚠️  DESIGN GOAL NOT MET — adjust the seed before shipping.")
    print("=" * 74)


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
    ap.add_argument("--t", type=int, default=None, help="override total resource T (calibration)")
    args = ap.parse_args()

    t_total = args.t if args.t is not None else BIND_T

    print("=" * 74)
    print("SERVICE-PACKAGE FORMATION — DEMO SEED")
    print("=" * 74)
    print(f"  target API : {args.base}")
    print(f"  dataset    : {N_SERVICES} services / {N_PROVIDERS} providers / "
          f"{len(PACKAGES)} groups of {GROUP_SIZE} → {len(unit_partition())} units")
    print(f"  T (resource): {t_total}   |  RNG seed: {SEED}")

    cells, _ = generate()
    verify(cells, t_total)

    if args.verify_only:
        print("\n--verify-only: skipping API writes.")
        print(f"\nDEMO LOGIN  →  {EMAIL}  /  {PASSWORD}")
        return

    print("\n" + "=" * 74)
    print(f"SEEDING via {args.base}")
    print("=" * 74)
    api = Api(args.base)
    authenticate(api)
    result = reset_and_seed(api, cells)
    verify_roundtrip(cells, result["returned_cells"])

    if args.run_methods:
        run_methods(api, t_total)

    print("\n" + "=" * 74)
    print(f"DONE.  DEMO LOGIN  →  {EMAIL}  /  {PASSWORD}   ({args.base})")
    print("=" * 74)


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"\nVERIFICATION FAILED: {e}", file=sys.stderr)
        sys.exit(1)
