FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    YAGL_DB_PATH=/data/yagl.sqlite3
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    useradd --system --uid 10001 --home-dir /app yagl && \
    mkdir -p /data && chown yagl:yagl /data
COPY backend ./backend
COPY frontend ./frontend
USER yagl
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)" || exit 1
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
