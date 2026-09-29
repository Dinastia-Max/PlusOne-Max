import unittest

from app.config import Settings


class DatabaseUrlTest(unittest.TestCase):
    def settings(self, database_url: str) -> Settings:
        return Settings(database_url=database_url, _env_file=None)

    def test_render_style_url_uses_asyncpg_driver(self):
        for url in (
            "postgres://user:pass@host:5432/db",
            "postgresql://user:pass@host:5432/db",
        ):
            with self.subTest(url=url):
                self.assertEqual(
                    self.settings(url).database_url,
                    "postgresql+asyncpg://user:pass@host:5432/db",
                )

    def test_explicit_driver_is_kept(self):
        url = "postgresql+asyncpg://user:pass@host:5432/db"

        self.assertEqual(self.settings(url).database_url, url)
