"""Fork addition: the OIDC wrapper around upstream's streamable HTTP app."""

from __future__ import annotations

from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.testclient import TestClient

from telegram_mcp.transport.http import ProtocolNegotiationMiddleware
from telegram_mcp.transport.oauth import wrap_app


class _Provider:
    required_scopes = ["openid"]

    def _get_resource_url(self, path):
        return None

    def get_routes(self, mcp_path):
        return []

    def get_middleware(self):
        return []


def test_lifespan_reaches_starlette_app_under_middleware():
    events = []

    @asynccontextmanager
    async def inner_lifespan(app):
        events.append("start")
        yield
        events.append("stop")

    # As create_streamable_http_app returns it: Starlette wrapped in middleware.
    inner = ProtocolNegotiationMiddleware(Starlette(lifespan=inner_lifespan))
    with TestClient(wrap_app(inner, _Provider())):
        assert events == ["start"]
    assert events == ["start", "stop"]
