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

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY ./app ./app
COPY ./tests ./tests
COPY ./database_migrations ./database_migrations
COPY ./pyproject.toml ./pyproject.toml

# Create non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# FastAPI will run on 8000 by default
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
