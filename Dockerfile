FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.lock pyproject.toml ./
COPY src ./src
RUN pip wheel --no-cache-dir --require-hashes -r requirements.lock --wheel-dir /wheels \
    && pip wheel --no-deps . --wheel-dir /wheels

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_MODE=demo
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels people-data-quality \
    && rm -rf /wheels \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data/local \
    && chown -R appuser:appuser /app
COPY ui ./ui
COPY .streamlit ./.streamlit
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "people_quality.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
