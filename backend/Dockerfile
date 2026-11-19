FROM rust:1.85.1-slim-bookworm AS rust_build
WORKDIR /rust-engine
COPY rust-engine/Cargo.toml rust-engine/Cargo.lock ./
COPY rust-engine/src ./src
RUN cargo build --release --locked

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMEGA_ENGINE_PATH=/usr/local/bin/omega-engine
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=rust_build /rust-engine/target/release/omega-engine /usr/local/bin/omega-engine
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini
RUN useradd --create-home --uid 10001 omega
USER omega
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
