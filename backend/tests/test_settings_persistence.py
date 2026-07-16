import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from routes import settings as settings_route


class SettingsPersistenceTests(unittest.TestCase):
    def test_backend_save_preserves_desktop_update_preferences(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "settings.json"
            path.write_text(
                json.dumps({
                    "theme": "dark",
                    "desktop_update_auto_check": False,
                    "desktop_update_auto_download": False,
                    "desktop_update_last_check_at": 1234.5,
                }),
                encoding="utf-8",
            )
            with patch.object(settings_route, "SETTINGS_PATH", str(path)):
                settings = settings_route.load_settings()
                settings.theme = "light"
                settings_route.save_settings(settings)

            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(saved["desktop_update_auto_check"])
            self.assertFalse(saved["desktop_update_auto_download"])
            self.assertEqual(saved["desktop_update_last_check_at"], 1234.5)


if __name__ == "__main__":
    unittest.main()
