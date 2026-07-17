import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import secure_settings
import storage
from crypto import encrypt_vault_with_key
from models import VaultData
from vault_document import encode_vault_document


class PasswordRekeyTransactionTests(unittest.TestCase):
    def tearDown(self):
        storage.lock_vault()

    def test_secure_file_write_failure_rolls_back_all_files_and_vault(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            paths = {
                "VAULT_PATH": str(root / "secretbase.enc"),
                "BACKUP_DIR": str(root / "backups"),
                "SETTINGS_PATH": str(root / "settings.json"),
                "SECURE_SETTINGS_FILE": str(root / "secure-settings.enc"),
                "AI_HISTORY_FILE": str(root / "ai-history.enc"),
                "SYNC_SETTINGS_FILE": str(root / "sync-settings.enc"),
                "SYNC_BASE_FILE": str(root / "sync-base.enc"),
            }
            with patch.multiple(storage, **paths):
                storage.lock_vault()
                self.assertTrue(storage.init_vault("old-main-password"))

                secure_files = [
                    (Path(paths["SECURE_SETTINGS_FILE"]), secure_settings.AI_SETTINGS_PURPOSE),
                    (Path(paths["AI_HISTORY_FILE"]), secure_settings.AI_HISTORY_PURPOSE),
                    (Path(paths["SYNC_SETTINGS_FILE"]), secure_settings.SYNC_SETTINGS_PURPOSE),
                    (Path(paths["SYNC_BASE_FILE"]), secure_settings.SYNC_BASE_PURPOSE),
                ]
                originals = {}
                for index, (path, purpose) in enumerate(secure_files):
                    purpose_key, salt = storage.derive_unlocked_purpose_key(purpose)
                    content = encrypt_vault_with_key(
                        purpose_key,
                        salt,
                        f'{{"fixture": {index}}}'.encode("utf-8"),
                    )
                    path.write_bytes(content)
                    originals[path] = content

                original_vault = Path(paths["VAULT_PATH"]).read_bytes()
                real_replace = secure_settings.replace_file_atomically
                write_count = 0

                def fail_third_write(path, content):
                    nonlocal write_count
                    write_count += 1
                    if write_count == 3:
                        raise OSError("simulated third secure file write failure")
                    real_replace(path, content)

                with patch.object(
                    secure_settings,
                    "replace_file_atomically",
                    side_effect=fail_third_write,
                ):
                    self.assertFalse(
                        storage.change_vault_password(
                            "old-main-password",
                            "new-main-password",
                        )
                    )

                self.assertEqual(Path(paths["VAULT_PATH"]).read_bytes(), original_vault)
                for path, content in originals.items():
                    self.assertEqual(path.read_bytes(), content)

                storage.lock_vault()
                self.assertTrue(storage.unlock_vault("old-main-password"))
                storage.lock_vault()
                self.assertFalse(storage.unlock_vault("new-main-password"))

    def test_vault_identity_import_failure_restores_sync_files_and_old_vault(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            paths = {
                "VAULT_PATH": str(root / "secretbase.enc"),
                "BACKUP_DIR": str(root / "backups"),
                "SETTINGS_PATH": str(root / "settings.json"),
                "SECURE_SETTINGS_FILE": str(root / "secure-settings.enc"),
                "AI_HISTORY_FILE": str(root / "ai-history.enc"),
                "SYNC_SETTINGS_FILE": str(root / "sync-settings.enc"),
                "SYNC_BASE_FILE": str(root / "sync-base.enc"),
            }
            with patch.multiple(storage, **paths):
                storage.lock_vault()
                self.assertTrue(storage.init_vault("main-password"))
                current = storage.get_vault_data()
                current.vault_id = "11111111-1111-4111-8111-111111111111"
                storage.save_vault_data(current)

                sync_settings = Path(paths["SYNC_SETTINGS_FILE"])
                sync_base = Path(paths["SYNC_BASE_FILE"])
                sync_settings.write_bytes(b"encrypted-sync-settings-fixture")
                sync_base.write_bytes(b"encrypted-sync-base-fixture")
                original_files = {
                    sync_settings: sync_settings.read_bytes(),
                    sync_base: sync_base.read_bytes(),
                }
                original_vault = Path(paths["VAULT_PATH"]).read_bytes()
                original_revision = storage.vault_revision()
                replacement = VaultData(vault_id="22222222-2222-4222-8222-222222222222")
                replacement_content = storage._encrypt_with_current_key(encode_vault_document(replacement))

                real_replace = secure_settings.replace_file_atomically
                write_count = 0

                def fail_second_write(path, content):
                    nonlocal write_count
                    write_count += 1
                    if write_count == 2:
                        raise OSError("simulated sync base deletion failure")
                    real_replace(path, content)

                with patch.object(
                    secure_settings,
                    "replace_file_atomically",
                    side_effect=fail_second_write,
                ):
                    with self.assertRaises(OSError):
                        storage.import_encrypted_vault(replacement_content)

                self.assertEqual(Path(paths["VAULT_PATH"]).read_bytes(), original_vault)
                self.assertEqual(storage.vault_revision(), original_revision)
                self.assertEqual(storage.get_vault_data().vault_id, current.vault_id)
                for path, content in original_files.items():
                    self.assertEqual(path.read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
