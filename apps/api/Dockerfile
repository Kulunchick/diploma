# ============================================================
# Stage 1: Build Rust extension (assignment_solver)
# ============================================================
FROM python:3.13-slim AS rust-builder

RUN apt-get update && apt-get install -y \
    build-essential curl pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"

RUN pip install maturin

WORKDIR /src
COPY libs/operations/src/ ./src/
COPY libs/operations/Cargo.toml libs/operations/Cargo.lock libs/operations/pyproject.toml ./

RUN maturin build --release --interpreter python3.13

# ============================================================
# Stage 2: Install Python dependencies
# ============================================================
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y \
    build-essential curl gcc pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Mirror repo layout so the ../../libs/shared path dep in uv.lock resolves:
#   /workspace/apps/api/../../libs/shared → /workspace/libs/shared  ✓
WORKDIR /workspace
COPY libs/shared/ libs/shared/
COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/

WORKDIR /workspace/apps/api
RUN uv sync --frozen --no-dev

# Override the PyPI assignment_solver with our local build
# (local build has set_iteration_callback; PyPI 0.5.0 does not)
COPY --from=rust-builder /src/target/wheels/ /wheels/
ENV VIRTUAL_ENV=/workspace/apps/api/.venv
RUN uv pip install /wheels/assignment_solver-*.whl --reinstall

# ============================================================
# Stage 3: Final runtime image
# ============================================================
FROM python:3.13-slim

COPY --from=builder /workspace/apps/api/.venv /app/.venv

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY apps/api/src src
# Alembic config + migrations live at the api root (next to src), so the
# startup hook and `alembic upgrade head` resolve them inside the container.
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/alembic ./alembic

CMD ["python", "-m", "src.operations.main"]
