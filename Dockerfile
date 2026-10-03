# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
# Copy only package.json, not package-lock.json.
# The lock file is generated on Windows and resolves only Windows-platform
# optional dependencies (e.g. lightningcss-win32-x64). npm install must run
# fresh inside this Linux container to pick up lightningcss-linux-x64-gnu.
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Build backend
FROM python:3.12-slim
WORKDIR /app
RUN pip install hatchling
COPY pyproject.toml README.md ./
RUN pip install .
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini
COPY --from=frontend-builder /frontend/dist ./frontend/dist
EXPOSE 8000
# Run migrations then start the server.
# DATABASE_URL must be provided via environment variable.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
