FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HAYSTACK_TELEMETRY_ENABLED=False
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY fde/ fde/
COPY config/ config/
COPY demo/ demo/
COPY reports/ reports/
COPY --from=web /web/dist web/dist
RUN useradd --uid 10001 --no-create-home desk
USER desk
EXPOSE 8790
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8790/healthz')"
CMD ["uvicorn", "fde.service.app:app", "--host", "0.0.0.0", "--port", "8790"]
