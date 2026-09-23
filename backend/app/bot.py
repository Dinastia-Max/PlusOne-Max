import asyncio
import logging
from typing import Any

import httpx

from app.config import get_settings


API_URL = "https://platform-api2.max.ru"
UPDATE_TYPES = "bot_started,message_created"
WELCOME_TEXT = (
    "Привет! Это ПлюсОдин.\n\n"
    "Здесь можно найти футбольную игру рядом или собрать свою. "
    "Мини-приложение скоро появится в этом чате."
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("plusone.bot")


class MaxBot:
    def __init__(self, token: str) -> None:
        timeout = httpx.Timeout(95.0, connect=15.0)
        self.client = httpx.AsyncClient(
            base_url=API_URL,
            headers={"Authorization": token},
            timeout=timeout,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def get_me(self) -> dict[str, Any]:
        response = await self.client.get("/me")
        response.raise_for_status()
        return response.json()

    async def get_updates(self, marker: int | None) -> dict[str, Any]:
        params: dict[str, str | int] = {
            "limit": 100,
            "timeout": 30,
            "types": UPDATE_TYPES,
        }
        if marker is not None:
            params["marker"] = marker

        response = await self.client.get("/updates", params=params)
        response.raise_for_status()
        return response.json()

    async def send_welcome(self, user_id: int) -> None:
        response = await self.client.post(
            "/messages",
            params={"user_id": user_id},
            json={"text": WELCOME_TEXT},
        )
        response.raise_for_status()


def get_user_id(update: dict[str, Any]) -> int | None:
    if update.get("update_type") == "bot_started":
        user = update.get("user") or {}
        return user.get("user_id")

    message = update.get("message") or {}
    sender = message.get("sender") or {}
    return sender.get("user_id")


def get_message_text(update: dict[str, Any]) -> str:
    message = update.get("message") or {}
    body = message.get("body") or {}
    return (body.get("text") or "").strip().lower()


async def handle_update(bot: MaxBot, update: dict[str, Any]) -> None:
    update_type = update.get("update_type")
    user_id = get_user_id(update)
    if user_id is None:
        logger.warning("Update %s has no user_id", update_type)
        return

    if update_type == "bot_started":
        await bot.send_welcome(user_id)
        return

    if update_type == "message_created":
        text = get_message_text(update)
        if text in {"/start", "start", "начать"}:
            await bot.send_welcome(user_id)


async def run() -> None:
    token = get_settings().max_bot_token.strip()
    if not token:
        raise RuntimeError("MAX_BOT_TOKEN is not configured")

    bot = MaxBot(token)
    marker: int | None = None
    try:
        me = await bot.get_me()
        logger.info(
            "Connected to MAX as @%s (id=%s)",
            me.get("username") or "unknown",
            me.get("user_id"),
        )

        while True:
            try:
                payload = await bot.get_updates(marker)
                for update in payload.get("updates", []):
                    await handle_update(bot, update)
                marker = payload.get("marker", marker)
            except httpx.HTTPError:
                logger.exception("MAX API request failed; retrying in 5 seconds")
                await asyncio.sleep(5)
    finally:
        await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
