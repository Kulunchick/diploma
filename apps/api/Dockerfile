# Етап збірки
FROM python:3.13-slim AS builder

# Встановлюємо системні залежності для збірки
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    gcc \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Фінальний етап
FROM python:3.13-slim

# Копіюємо лише необхідні бібліотеки з етапу збірки
COPY --from=builder /app/.venv /app/.venv

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH"
COPY src src
CMD ["python", "-m", "src.coursework_operations.main"]