# Paper / demo-via-ccxt runner. MT5 needs Windows: see docs/DEPLOY.md.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt telethon ccxt
COPY goldbot ./goldbot
COPY config ./config
COPY scripts ./scripts
RUN useradd --create-home --uid 10001 goldbot && mkdir -p /app/state && chown -R goldbot /app/state
USER goldbot
VOLUME ["/app/state"]
HEALTHCHECK --interval=10m --timeout=10s --start-period=2m \
  CMD python -c "import pathlib,time,sys; p=[*pathlib.Path('/app/state').glob('*/goldbot.log')]; sys.exit(0 if p and time.time()-max(x.stat().st_mtime for x in p)<7200 else 1)"
ENTRYPOINT ["python", "-m", "goldbot"]
CMD ["run"]
