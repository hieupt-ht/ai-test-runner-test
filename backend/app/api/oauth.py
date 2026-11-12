"""Đăng nhập bằng Google (OAuth).

`OAuthClient` là Protocol để test có thể thay bằng Google giả.
"""

from typing import Any, Protocol

from authlib.integrations.starlette_client import OAuth
from fastapi import Request
from fastapi.responses import Response
from pydantic import BaseModel

GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"


class GoogleIdentity(BaseModel):
    email: str
    name: str


class OAuthClient(Protocol):
    async def authorize_redirect(self, request: Request, redirect_uri: str) -> Response: ...

    async def fetch_identity(self, request: Request) -> GoogleIdentity: ...


class GoogleOAuth:
    """Cài đặt thật dùng thư viện Authlib."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._oauth = OAuth()
        self._oauth.register(
            name="google",
            client_id=client_id,
            client_secret=client_secret,
            server_metadata_url=GOOGLE_METADATA_URL,
            client_kwargs={"scope": "openid email profile"},
        )

    async def authorize_redirect(self, request: Request, redirect_uri: str) -> Response:
        response: Response = await self._oauth.google.authorize_redirect(request, redirect_uri)
        return response

    async def fetch_identity(self, request: Request) -> GoogleIdentity:
        token: dict[str, Any] = await self._oauth.google.authorize_access_token(request)
        userinfo = token.get("userinfo") or {}
        return GoogleIdentity(
            email=str(userinfo.get("email", "")), name=str(userinfo.get("name", ""))
        )
