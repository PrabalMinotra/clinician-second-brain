FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run check && npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SECOND_BRAIN_RUNTIME=/var/data
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.lock.txt backend/requirements.lock.txt
COPY deploy/requirements.txt deploy/requirements.txt
RUN pip install --no-cache-dir -r deploy/requirements.txt
RUN useradd --create-home app && mkdir /var/data && chown app:app /var/data
COPY backend/ backend/
COPY fixtures/ fixtures/
COPY --from=frontend /build/dist frontend/dist
COPY deploy/start.sh deploy/start.sh
USER app
EXPOSE 8000
CMD ["bash", "deploy/start.sh"]
