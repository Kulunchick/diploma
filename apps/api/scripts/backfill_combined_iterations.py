"""One-shot backfill: repair the convergence history of pre-existing combined
scenarios stored before the best-so-far telemetry fix.

Older combined runs concatenated several independent local-search passes into
one series, producing mid-chart drops and a discontinuous X axis. This salvages
that history in place WITHOUT re-running the solver:

  * read the scenario's formation_iterations ordered by iteration;
  * recompute best_value as a running max (monotone non-decreasing);
  * renumber iterations contiguously 1..N;
  * force the final point to equal the stored combined benefit
    (value + provider_value) so the chart ends exactly on the result cards.

Idempotent: running it again on already-clean data is a no-op (running max of a
monotone series is itself; renumbering a contiguous series is itself).

Run from the repo root with the API venv:
    python apps/api/scripts/backfill_combined_iterations.py
"""
import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://diploma:diploma@localhost:5432/diploma"
)


async def main() -> None:
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        scenarios = (
            await conn.execute(
                text(
                    "SELECT id, value, provider_value FROM formation_scenarios "
                    "WHERE algorithm = 'combined' AND status = 'completed'"
                )
            )
        ).all()

        print(f"Found {len(scenarios)} completed combined scenario(s).")
        for sid, value, provider_value in scenarios:
            rows = (
                await conn.execute(
                    text(
                        "SELECT iteration, best_value FROM formation_iterations "
                        "WHERE scenario_id = :sid ORDER BY iteration"
                    ),
                    {"sid": sid},
                )
            ).all()
            if not rows:
                print(f"  {sid}: no iteration rows — skipped")
                continue

            benefit = float(value or 0) + float(provider_value or 0)

            # Running max over the existing values, renumbered contiguously.
            running = float("-inf")
            cleaned: list[float] = []
            for _it, bv in rows:
                running = max(running, float(bv))
                cleaned.append(running)
            # Final point must match the combined benefit on the result cards.
            if benefit > cleaned[-1]:
                cleaned.append(benefit)
            else:
                cleaned[-1] = max(cleaned[-1], benefit)

            had_drop = any(
                float(rows[i + 1][1]) < float(rows[i][1]) - 1e-9 for i in range(len(rows) - 1)
            )
            had_gap = [r[0] for r in rows] != list(range(rows[0][0], rows[0][0] + len(rows)))

            # Rewrite the whole series atomically: delete then re-insert 1..N.
            await conn.execute(
                text("DELETE FROM formation_iterations WHERE scenario_id = :sid"),
                {"sid": sid},
            )
            for i, bv in enumerate(cleaned, start=1):
                await conn.execute(
                    text(
                        "INSERT INTO formation_iterations (scenario_id, iteration, best_value) "
                        "VALUES (:sid, :it, :bv)"
                    ),
                    {"sid": sid, "it": i, "bv": bv},
                )
            print(
                f"  {sid}: {len(rows)}→{len(cleaned)} pts  "
                f"end={cleaned[-1]:.0f} (benefit={benefit:.0f})  "
                f"fixed_drop={had_drop} fixed_gap={had_gap}"
            )

    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
