import unittest
from unittest.mock import AsyncMock, Mock

from app.bot import BOT_COMMANDS, MaxBot


class WelcomeMessageTest(unittest.IsolatedAsyncioTestCase):
    async def test_open_app_button_uses_bot_username(self):
        response = Mock(is_success=True)
        bot = MaxBot.__new__(MaxBot)
        bot.web_app = "plusone_bot"
        bot.client = Mock()
        bot.client.post = AsyncMock(return_value=response)

        await bot.send_welcome(user_id=42)

        body = bot.client.post.await_args.kwargs["json"]
        button = body["attachments"][0]["payload"]["buttons"][0][0]
        self.assertEqual(button["type"], "open_app")
        self.assertEqual(button["web_app"], "plusone_bot")
        response.raise_for_status.assert_called_once_with()

    async def test_registers_start_command(self):
        response = Mock()
        bot = MaxBot.__new__(MaxBot)
        bot.client = Mock()
        bot.client.patch = AsyncMock(return_value=response)

        await bot.set_commands()

        bot.client.patch.assert_awaited_once_with(
            "/me/commands",
            json={"commands": BOT_COMMANDS},
        )
        response.raise_for_status.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
