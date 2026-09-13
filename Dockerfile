FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY certs ./certs
COPY static ./static

RUN pip install --no-cache-dir hatchling \
    && pip install --no-cache-dir . \
    && chmod -R a+rX /app/static

ENV MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=3001 \
    WEBQUIK_HOST=webquik.sberbank.ru \
    WEBQUIK_CA_BUNDLE=/app/certs/sberca-chain.pem \
    WEBQUIK_SSL_VERIFY=true

EXPOSE 3001

USER nobody

CMD ["mcp-over-quik"]
