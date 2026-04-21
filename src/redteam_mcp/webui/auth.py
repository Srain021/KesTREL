from __future__ import annotations

import os
import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ..config import WebUISettings

_security = HTTPBasic(auto_error=False)


def _challenge() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Basic"},
    )


def _expected_username(settings: WebUISettings) -> str:
    return os.getenv("KESTREL_WEB_USER") or settings.username


def _expected_password(settings: WebUISettings) -> str:
    return os.getenv("KESTREL_WEB_PASS") or os.getenv("KESTREL_WEB_TOKEN") or ""


def build_basic_auth_dependency(
    settings: WebUISettings,
) -> Callable[[HTTPBasicCredentials | None], Awaitable[None]]:
    async def verify_auth(
        credentials: Annotated[HTTPBasicCredentials | None, Depends(_security)],
    ) -> None:
        if not settings.auth_required:
            return

        expected_password = _expected_password(settings)
        if credentials is None or not expected_password:
            raise _challenge()

        username_ok = secrets.compare_digest(credentials.username, _expected_username(settings))
        password_ok = secrets.compare_digest(credentials.password, expected_password)
        if not (username_ok and password_ok):
            raise _challenge()

    return verify_auth
