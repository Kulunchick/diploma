# ============================================================
# Stage 1: Build Rust extension (assignment_solver)
# Needed because PyPI 0.5.0 lacks set_iteration_callback.
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
    curl gcc pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install shared lib and worker package together so uv resolves the
# shared path dependency without hitting PyPI.
COPY libs/shared/ /shared/
COPY apps/worker/ /worker/
RUN uv venv .venv
ENV VIRTUAL_ENV=/app/.venv
RUN uv pip install /shared/ /worker/

# Override the PyPI assignment_solver with our local Rust build.
COPY --from=rust-builder /src/target/wheels/ /wheels/
RUN uv pip install /wheels/assignment_solver-*.whl --reinstall --no-deps

# ============================================================
# Stage 3: Final runtime image
# ============================================================
FROM python:3.13-slim

COPY --from=builder /app/.venv /app/.venv

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "worker.main"]
