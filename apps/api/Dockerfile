# ============================================================
# Stage 1: Build Rust extension (assignment_solver)
# ============================================================
FROM python:3.13-slim AS rust-builder

RUN apt-get update && apt-get install -y \
    build-essential curl pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"

RUN pip install maturin

WORKDIR /src
# Copy only source files — skip target/ (large Rust build cache)
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

WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev

# Override the PyPI assignment_solver with our local build
# (local build has set_iteration_callback; PyPI 0.5.0 does not)
COPY --from=rust-builder /src/target/wheels/ /wheels/
ENV VIRTUAL_ENV=/app/.venv
RUN uv pip install /wheels/assignment_solver-*.whl --reinstall

# ============================================================
# Stage 3: Final runtime image
# ============================================================
FROM python:3.13-slim

COPY --from=builder /app/.venv /app/.venv

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

# Install the worker package (worker + experiments) into the same venv.
# Its dependencies (pydantic, temporalio, redis, numpy) are already satisfied
# by the api's uv sync above — so --no-deps avoids redundant reinstalls.
COPY apps/worker/ /worker/
ENV VIRTUAL_ENV=/app/.venv
RUN uv pip install /worker/ --no-deps

COPY apps/api/src src

CMD ["python", "-m", "src.coursework_operations.main"]
