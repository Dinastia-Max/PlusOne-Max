import os
import unittest
from unittest.mock import patch

from app.config import get_settings


class ConfiguredAuthTestCase(unittest.TestCase):
    def setUp(self):
        self._environment = patch.dict(
            os.environ,
            {"MAX_BOT_TOKEN": "test-bot-token"},
        )
        self._environment.start()
        get_settings.cache_clear()

    def tearDown(self):
        get_settings.cache_clear()
        self._environment.stop()
