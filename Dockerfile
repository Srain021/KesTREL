FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY config ./config
RUN pip install --no-cache-dir "uv>=0.5" \
    && uv venv /opt/venv \
    && uv pip install --python /opt/venv/bin/python --no-cache .

FROM python:3.12-slim

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY config ./config

ENTRYPOINT ["kestrel"]
CMD ["serve"]
