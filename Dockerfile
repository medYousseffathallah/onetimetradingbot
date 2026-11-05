# Optional offline-demo container. Review/pin a base-image digest before deployment.
FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --chown=app:app src/ ./src/
COPY --chown=app:app tests/fixtures/ ./tests/fixtures/
COPY --chown=app:app configs/ ./configs/
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER app
CMD ["python", "-m", "bvmt.cli", "demo"]
