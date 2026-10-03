FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/argate
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
WORKDIR /workspace
ENTRYPOINT ["argate"]
# Clarify implementation notes for dockerfile
