# Fork (sgorblex/telegram-mcp): the MCP server as streamable HTTP on :8000/mcp behind an
# OAuth proxy (TELEGRAM_MCP_AUTH=oidc), with a persistent file session under /session.
# Upstream's Dockerfile stays as it is, for the unauthenticated loopback setup.
FROM ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie-slim
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY *.py ./
COPY telegram_mcp ./telegram_mcp
# Installs the project itself too, for the telegram-mcp-login entry point.
RUN uv sync --locked --no-dev --no-editable
RUN useradd --uid 1000 --create-home telegram \
    && install -d -o telegram -g telegram /session /oauth
USER telegram
# TELEGRAM_EXPOSED_TOOLS: the deployment sets its own; this default keeps a bare
# `podman run` from exposing deletes and admin tools.
ENV PATH=/app/.venv/bin:$PATH \
    MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    TELEGRAM_MCP_AUTH=oidc \
    TELEGRAM_SESSION_NAME=/session/telegram \
    TELEGRAM_EXPOSED_TOOLS=read-only \
    FASTMCP_HOME=/oauth \
    FASTMCP_SHOW_SERVER_BANNER=false \
    FASTMCP_CHECK_FOR_UPDATES=off
VOLUME /session /oauth
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)"]
CMD ["telegram-mcp"]
