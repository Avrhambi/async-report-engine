FROM python:3.11-slim as builder

WORKDIR /app

# Install dependencies required for building python packages (e.g., asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim as runner

WORKDIR /app

# Install runtime dependencies for postgres
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user first so we can own the deps to it
RUN useradd -m appuser

# Copy installed packages from builder into the appuser home so the
# non-root runtime user can execute console scripts (pytest, celery, …).
# /root/.local is mode 700 and unreadable to appuser, so it can't live there.
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application code
COPY --chown=appuser:appuser ./app ./app
COPY --chown=appuser:appuser ./tests ./tests
COPY --chown=appuser:appuser ./database_migrations ./database_migrations
COPY --chown=appuser:appuser ./pyproject.toml ./pyproject.toml

RUN chown -R appuser /app
USER appuser

# FastAPI will run on 8000 by default
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
