import hashlib
import hmac
import json
import re
import time
from typing import Annotated
from urllib.parse import unquote

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings


class MaxInitDataError(ValueError):
    pass


def validate_max_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int,
    *,
    now: float | None = None,
) -> int:
    if not init_data or not bot_token or max_age_seconds <= 0:
        raise MaxInitDataError

    params: dict[str, str] = {}
    for item in init_data.split("&"):
        key, separator, value = item.partition("=")
        if not separator or not key:
            raise MaxInitDataError

        try:
            key = unquote(key, errors="strict")
            value = unquote(value, errors="strict")
        except UnicodeDecodeError as exc:
            raise MaxInitDataError from exc
        if key in params:
            raise MaxInitDataError
        params[key] = value

    original_hash = params.pop("hash", None)
    if original_hash is None:
        raise MaxInitDataError

    launch_params = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        secret_key,
        launch_params.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(calculated_hash, original_hash):
        raise MaxInitDataError

    try:
        auth_date = int(params["auth_date"])
        user = json.loads(params["user"])
        user_id = user["id"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MaxInitDataError from exc

    current_time = time.time() if now is None else now
    if auth_date > current_time + 30:
        raise MaxInitDataError
    if current_time - auth_date > max_age_seconds:
        raise MaxInitDataError
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise MaxInitDataError

    return user_id


async def get_current_user_id(
    settings: Annotated[Settings, Depends(get_settings)],
    init_data: Annotated[
        str | None,
        Header(alias="X-Max-Init-Data"),
    ] = None,
) -> int:
    if not settings.max_bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MAX authentication is not configured",
        )

    try:
        return validate_max_init_data(
            init_data or "",
            settings.max_bot_token,
            settings.max_auth_max_age_seconds,
        )
    except MaxInitDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MAX init data",
            headers={"WWW-Authenticate": "MaxInitData"},
        ) from exc


MAX_USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,64}")


def extract_max_username(init_data: str | None) -> str | None:
    """Returns the public username from already validated init data."""
    for item in (init_data or "").split("&"):
        key, _, value = item.partition("=")
        if unquote(key) != "user":
            continue
        try:
            username = json.loads(unquote(value)).get("username")
        except (AttributeError, ValueError):
            return None
        if isinstance(username, str):
            username = username.strip().removeprefix("@")
            if MAX_USERNAME_PATTERN.fullmatch(username):
                return username
        return None
    return None


async def get_current_username(
    _user_id: Annotated[int, Depends(get_current_user_id)],
    init_data: Annotated[
        str | None,
        Header(alias="X-Max-Init-Data"),
    ] = None,
) -> str | None:
    return extract_max_username(init_data)


async def get_optional_current_user_id(
    settings: Annotated[Settings, Depends(get_settings)],
    init_data: Annotated[
        str | None,
        Header(alias="X-Max-Init-Data"),
    ] = None,
) -> int | None:
    if init_data is None:
        return None
    return await get_current_user_id(settings=settings, init_data=init_data)
