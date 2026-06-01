"""Provider-side metrics derived from a frozen formation snapshot + a result
matrix. Shared by all three persist paths so F_prov / provider_profit are
computed by exactly one piece of code (no per-algorithm copy-paste).

Definitions, for a scenario with assignment matrix v, prices d_ij, provider
revenues p_ij and discounts r_ij:

    F_prov          = Σ_ij p_ij·v_ij                 (gross provider revenue)
    provider_profit = Σ_ij (p_ij − (1 − r_ij)·d_ij)·v_ij
    total_value     = Σ_ij p_ij·v_ij                 (== F_prov)

p_ij is the provider's revenue from its OWN end-clients; the IT-company's
discount r_ij does not touch it (it only changes (1 − r)·d_ij, the price the
provider pays the IT-company). This refines the article's formula (2) — see
docs/combined-method.md. Because (1 − r_ij)·d_ij is the IT-company's per-pair
revenue, system-wide

    F_IT + provider_profit == Σ p·v == F_prov

an exact identity, asserted warn-only in the persist activities. Note F_prov no
longer depends on r at all; r matters only for provider_profit.
"""
from typing import Optional


def compute_provider_metrics(
    service_cells: dict,
    unit_order: list,
    v: list,
    final_discount: Optional[list] = None,
) -> tuple[float, float, float]:
    """Return (f_prov, provider_profit, total_value) for the given solution.

    v is the unit×provider assignment matrix; each selected unit expands to its
    member services using the per-service price/provider_revenue/discount frozen
    in ``service_cells``. ``r`` is ``final_discount[u][j]`` when provided (the
    combined method's negotiated discount, applied to the whole unit) and the
    per-service planning discount otherwise (probabilistic / ant-colony never
    move the discount). r affects only provider_profit — F_prov is raw Σp·v.
    """
    f_prov = 0.0
    provider_profit = 0.0
    total_value = 0.0
    for u_index, unit in enumerate(unit_order):
        for j, selected in enumerate(v[u_index]):
            if int(selected) != 1:
                continue
            r_unit = (
                float(final_discount[u_index][j]) if final_discount is not None else None
            )
            for service_id in unit["service_ids"]:
                sc = service_cells[service_id]
                d = float(sc["price"][j])
                p = float(sc["provider_revenue"][j])
                r = r_unit if r_unit is not None else float(sc["discount"][j])
                paid_to_it = (1.0 - r) * d
                f_prov += p  # raw client-side revenue, no discount factor
                provider_profit += p - paid_to_it
                total_value += p
    return f_prov, provider_profit, total_value
