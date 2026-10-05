# Paper / demo-via-ccxt runner. MT5 needs Windows: see docs/DEPLOY.md.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt telethon ccxt
COPY goldbot ./goldbot
COPY config ./config
COPY scripts ./scripts
COPY deploy/docker-entrypoint.sh /usr/local/bin/goldbot-entrypoint
RUN useradd --create-home --uid 10001 goldbot && mkdir -p /app/state && chown -R goldbot /app/state \
    && chmod +x /usr/local/bin/goldbot-entrypoint
VOLUME ["/app/state"]
# healthy if the log is fresh, or the gold market is closed (weekends)
HEALTHCHECK --interval=10m --timeout=20s --start-period=5m \
  CMD setpriv --reuid=goldbot --regid=goldbot --init-groups python -m goldbot health
ENTRYPOINT ["goldbot-entrypoint"]
CMD ["run"]
