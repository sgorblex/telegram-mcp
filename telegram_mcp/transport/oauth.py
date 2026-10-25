"""OAuth for the streamable HTTP transport, proxied to an upstream OpenID provider.

Fork addition (sgorblex/telegram-mcp). Upstream's HTTP endpoint is unauthenticated
and meant for loopback only. With ``TELEGRAM_MCP_AUTH=oidc`` the upstream app is
mounted behind fastmcp's ``OIDCProxy``: MCP clients (claude.ai) register
dynamically with this server, the user signs in at the provider (e.g. authentik,
which decides who may), and every request to the MCP endpoint needs a bearer
token this server issued. Client registrations and upstream tokens are kept
encrypted under ``FASTMCP_HOME``.

Kept in its own module so the rest of the tree stays identical to upstream.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route

AUTH_MODES = ("none", "oidc")
MCP_PATH = "/mcp"
DEFAULT_REDIRECT_URIS = (
    "https://claude.ai/api/mcp/auth_callback,https://claude.com/api/mcp/auth_callback"
)


def auth_mode() -> str:
    """``TELEGRAM_MCP_AUTH``: none (default, as upstream) | oidc."""
    mode = (os.getenv("TELEGRAM_MCP_AUTH") or "none").strip().lower()
    if mode not in AUTH_MODES:
        raise SystemExit(
            f"Invalid TELEGRAM_MCP_AUTH '{mode}'. Expected one of: {', '.join(AUTH_MODES)}."
        )
    return mode


def _env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"{name} is required with TELEGRAM_MCP_AUTH=oidc")
    return value


def build_provider() -> Any:
    from fastmcp.server.auth.oidc_proxy import OIDCProxy

    redirect_uris = os.getenv("TELEGRAM_MCP_ALLOWED_REDIRECT_URIS", DEFAULT_REDIRECT_URIS)
    return OIDCProxy(
        config_url=_env("TELEGRAM_MCP_OIDC_CONFIG_URL"),
        client_id=_env("TELEGRAM_MCP_OIDC_CLIENT_ID"),
        client_secret=_env("TELEGRAM_MCP_OIDC_CLIENT_SECRET"),
        base_url=_env("TELEGRAM_MCP_BASE_URL"),
        jwt_signing_key=_env("TELEGRAM_MCP_JWT_SIGNING_KEY"),
        allowed_client_redirect_uris=[u.strip() for u in redirect_uris.split(",") if u.strip()],
        required_scopes=["openid"],
        # Asked of the provider whatever the client requests. Without offline_access the
        # provider issues no refresh token, so the client must sign in again each time
        # the access token expires (authentik: 5 minutes by default).
        extra_authorize_params={
            "scope": os.getenv("TELEGRAM_MCP_OIDC_UPSTREAM_SCOPES", "openid offline_access"),
        },
    )


def validate_config() -> None:
    """Fail at startup, naming the variable, rather than on the first request."""
    if auth_mode() == "oidc":
        if (os.getenv("MCP_TRANSPORT") or "stdio").lower() == "sse":
            raise SystemExit("TELEGRAM_MCP_AUTH=oidc protects MCP_TRANSPORT=http only, not sse")
        for name in (
            "TELEGRAM_MCP_OIDC_CONFIG_URL",
            "TELEGRAM_MCP_OIDC_CLIENT_ID",
            "TELEGRAM_MCP_OIDC_CLIENT_SECRET",
            "TELEGRAM_MCP_BASE_URL",
            "TELEGRAM_MCP_JWT_SIGNING_KEY",
        ):
            _env(name)


async def _healthz(request: Request) -> PlainTextResponse:
    """Up, with every Telegram client connected. Not behind auth."""
    from telegram_mcp.runtime import clients

    down = [label for label, client in clients.items() if not client.is_connected()]
    if not clients or down:
        return PlainTextResponse(f"disconnected: {', '.join(down) or 'no clients'}", 503)
    return PlainTextResponse("ok")


def wrap_app(inner: Starlette, provider: Any) -> Starlette:
    """Put ``inner`` (upstream's streamable HTTP app) behind ``provider``."""
    from fastmcp.server.auth.middleware import RequireAuthMiddleware
    from mcp.server.auth.routes import build_resource_metadata_url

    resource_url = provider._get_resource_url(MCP_PATH)
    resource_metadata_url = build_resource_metadata_url(resource_url) if resource_url else None

    @asynccontextmanager
    async def lifespan(app: Starlette):
        # Mount does not forward lifespan events; upstream's app starts its session
        # manager in its own lifespan.
        async with inner.router.lifespan_context(inner):
            yield

    routes = [
        *provider.get_routes(mcp_path=MCP_PATH),
        Route("/healthz", _healthz, methods=["GET"]),
        Mount(
            "/",
            app=RequireAuthMiddleware(inner, provider.required_scopes, resource_metadata_url),
        ),
    ]
    return Starlette(routes=routes, middleware=provider.get_middleware(), lifespan=lifespan)


async def run_streamable_http_oidc(mcp_instance: Any) -> None:
    import uvicorn

    from telegram_mcp.transport.http import create_streamable_http_app

    app = wrap_app(create_streamable_http_app(mcp_instance), build_provider())
    config = uvicorn.Config(
        app,
        host=mcp_instance.settings.host,
        port=mcp_instance.settings.port,
        log_level=mcp_instance.settings.log_level.lower(),
    )
    await uvicorn.Server(config).serve()
