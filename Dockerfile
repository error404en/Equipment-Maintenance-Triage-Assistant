# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Build backend
FROM python:3.12-slim
WORKDIR /app
RUN pip install hatchling
COPY pyproject.toml ./
RUN pip install .
COPY app/ ./app/
COPY --from=frontend-builder /frontend/dist ./frontend/dist
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
