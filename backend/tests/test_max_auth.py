import hashlib
import hmac
import json
import time
import unittest
from urllib.parse import quote

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import (
    MaxInitDataError,
    get_current_user_id,
    validate_max_init_data,
)
from app.main import app


BOT_TOKEN = "test-bot-token"
USER_ID = 476177021


def signed_init_data(
    *,
    auth_date: int | None = None,
    user: dict | None = None,
    token: str = BOT_TOKEN,
) -> str:
    params = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "test-query-id",
        "user": json.dumps(
            user or {"id": USER_ID, "first_name": "Test"},
            separators=(",", ":"),
            ensure_ascii=False,
        ),
    }
    launch_params = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        token.encode(),
        hashlib.sha256,
    ).digest()
    params["hash"] = hmac.new(
        secret_key,
        launch_params.encode(),
        hashlib.sha256,
    ).hexdigest()
    return "&".join(
        f"{key}={quote(value, safe='')}" for key, value in params.items()
    )


class MaxInitDataValidationTest(unittest.TestCase):
    def test_returns_user_id_for_valid_data(self):
        now = int(time.time())

        user_id = validate_max_init_data(
            signed_init_data(auth_date=now),
            BOT_TOKEN,
            3600,
            now=now,
        )

        self.assertEqual(user_id, USER_ID)

    def test_rejects_modified_data(self):
        init_data = signed_init_data().replace("Test", "Changed")

        with self.assertRaises(MaxInitDataError):
            validate_max_init_data(init_data, BOT_TOKEN, 3600)

    def test_rejects_expired_data(self):
        now = int(time.time())

        with self.assertRaises(MaxInitDataError):
            validate_max_init_data(
                signed_init_data(auth_date=now - 3601),
                BOT_TOKEN,
                3600,
                now=now,
            )

    def test_rejects_data_from_future(self):
        now = int(time.time())

        with self.assertRaises(MaxInitDataError):
            validate_max_init_data(
                signed_init_data(auth_date=now + 31),
                BOT_TOKEN,
                3600,
                now=now,
            )

    def test_rejects_duplicate_hash(self):
        init_data = signed_init_data()

        with self.assertRaises(MaxInitDataError):
            validate_max_init_data(
                f"{init_data}&hash=duplicate",
                BOT_TOKEN,
                3600,
            )

    def test_rejects_invalid_encoding(self):
        with self.assertRaises(MaxInitDataError):
            validate_max_init_data("hash=%FF", BOT_TOKEN, 3600)

    def test_rejects_invalid_user(self):
        with self.assertRaises(MaxInitDataError):
            validate_max_init_data(
                signed_init_data(user={"id": 0}),
                BOT_TOKEN,
                3600,
            )


class CurrentUserDependencyTest(unittest.IsolatedAsyncioTestCase):
    def settings(self, token: str = BOT_TOKEN) -> Settings:
        return Settings(
            database_url="sqlite+aiosqlite://",
            max_bot_token=token,
            max_auth_max_age_seconds=3600,
            _env_file=None,
        )

    async def test_extracts_signed_user_id(self):
        user_id = await get_current_user_id(
            settings=self.settings(),
            init_data=signed_init_data(),
        )

        self.assertEqual(user_id, USER_ID)

    async def test_missing_data_is_unauthorized(self):
        with self.assertRaises(HTTPException) as context:
            await get_current_user_id(
                settings=self.settings(),
                init_data=None,
            )

        self.assertEqual(context.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    async def test_missing_bot_token_is_service_unavailable(self):
        with self.assertRaises(HTTPException) as context:
            await get_current_user_id(
                settings=self.settings(token=""),
                init_data=signed_init_data(),
            )

        self.assertEqual(
            context.exception.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class CorsTest(unittest.TestCase):
    def test_allows_max_auth_header_from_miniapp(self):
        response = TestClient(app).options(
            "/users/me/slots",
            headers={
                "Origin": "http://localhost:8080",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Max-Init-Data",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:8080",
        )
        self.assertIn(
            "x-max-init-data",
            response.headers["access-control-allow-headers"].lower(),
        )


if __name__ == "__main__":
    unittest.main()
