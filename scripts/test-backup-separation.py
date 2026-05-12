from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import storage  # noqa: E402
from models import Entry  # noqa: E402
from routes import transfer  # noqa: E402
from routes import settings as settings_route  # noqa: E402


def reset_storage(tmpdir: Path, max_backups: int = 5, auto_backup_retention: int | None = None) -> None:
    storage.lock_vault()
    data_dir = tmpdir / "data"
    backup_dir = data_dir / "backups"
    data_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    storage.VAULT_PATH = str(data_dir / "secretbase.enc")
    storage.BACKUP_DIR = str(backup_dir)
    storage.SETTINGS_PATH = str(data_dir / "settings.json")
    settings_route.SETTINGS_PATH = storage.SETTINGS_PATH
    Path(settings_route.SETTINGS_PATH).write_text(
        json.dumps({"auto_backup_retention": auto_backup_retention or max_backups}),
        encoding="utf-8"
    )

    assert storage.init_vault("correct horse battery staple")


def write_entry(title: str) -> None:
    vault = storage.get_vault_data()
    vault.entries.append(Entry(title=title))
    storage.save_vault_data(vault)


def test_manual_backup_uses_manual_dir_and_survives_auto_cleanup() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmpdir = Path(raw)
        reset_storage(tmpdir, max_backups=5)

        manual_path = storage.create_backup()
        assert manual_path.parent.name == "manual"

        for index in range(5):
            write_entry(f"Entry {index}")

        auto_backups = sorted((tmpdir / "data" / "backups" / "auto").glob("*.bak"))
        assert len(auto_backups) <= 5
        assert manual_path.exists()


def test_legacy_root_backups_are_migrated_to_auto_dir() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmpdir = Path(raw)
        reset_storage(tmpdir, max_backups=5)
        backup_dir = tmpdir / "data" / "backups"
        legacy_path = backup_dir / "secretbase.enc.20250101_000000_000000.bak"
        legacy_path.write_bytes(Path(storage.VAULT_PATH).read_bytes())

        storage.create_backup()

        migrated_path = backup_dir / "auto" / legacy_path.name
        assert not legacy_path.exists()
        assert migrated_path.exists()


def test_backup_list_reports_manual_and_auto_types() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmpdir = Path(raw)
        reset_storage(tmpdir, max_backups=5)

        manual_path = storage.create_backup()
        write_entry("Auto backup trigger")

        result = asyncio.run(transfer.list_backups())
        items = result["data"]["items"]
        types_by_name = {item["filename"]: item["type"] for item in items}

        assert types_by_name[manual_path.name] == "manual"
        assert "auto" in types_by_name.values()


def test_auto_backup_cleanup_uses_settings_retention() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmpdir = Path(raw)
        reset_storage(tmpdir, max_backups=30, auto_backup_retention=5)

        manual_paths = [storage.create_backup() for _ in range(2)]
        for index in range(7):
            write_entry(f"Entry {index}")

        auto_backups = sorted((tmpdir / "data" / "backups" / "auto").glob("*.bak"))
        assert len(auto_backups) <= 5
        assert all(path.exists() for path in manual_paths)


def test_backup_list_includes_display_and_download_names() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmpdir = Path(raw)
        reset_storage(tmpdir, max_backups=5)

        manual_path = storage.create_backup()
        result = asyncio.run(transfer.list_backups())
        item = next(item for item in result["data"]["items"] if item["filename"] == manual_path.name)

        assert item["display_name"].startswith("手动备份-")
        assert item["download_name_encrypted"].startswith("手动备份-")
        assert item["download_name_encrypted"].endswith(".bak")
        assert item["download_name_plain"].endswith(".json")


def test_backup_downloads_encrypted_and_plain_with_confirmation() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmpdir = Path(raw)
        reset_storage(tmpdir, max_backups=5)
        write_entry("Exportable")
        manual_path = storage.create_backup()

        encrypted_response = asyncio.run(transfer.download_backup_encrypted(manual_path.name))
        assert encrypted_response.body == manual_path.read_bytes()
        assert "filename*=UTF-8''" in encrypted_response.headers["content-disposition"]

        try:
            asyncio.run(transfer.download_backup_plain(manual_path.name, {}))
            raise AssertionError("plain download without confirmation should fail")
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 422

        plain_response = asyncio.run(transfer.download_backup_plain(manual_path.name, {"confirm": True}))
        plain = json.loads(plain_response.body.decode("utf-8"))
        assert plain["entries"][0]["title"] == "Exportable"
        assert "filename*=UTF-8''" in plain_response.headers["content-disposition"]


def test_backup_summary_includes_current_vault_counts() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmpdir = Path(raw)
        reset_storage(tmpdir, max_backups=5)
        write_entry("Before backup")
        manual_path = storage.create_backup()
        write_entry("After backup")

        result = asyncio.run(transfer.get_backup_summary(manual_path.name))
        data = result["data"]

        assert data["entry_count"] == 1
        assert data["deleted_count"] == 0
        assert data["current_entry_count"] == 2
        assert data["current_deleted_count"] == 0


def test_plain_backup_download_requires_correct_legacy_password() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmpdir = Path(raw)
        reset_storage(tmpdir, max_backups=5)
        write_entry("Before password change")
        manual_path = storage.create_backup()
        assert storage.change_vault_password("correct horse battery staple", "new correct horse battery staple")

        try:
            asyncio.run(transfer.download_backup_plain(manual_path.name, {"confirm": True}))
            raise AssertionError("legacy plain download without password should fail")
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 422

        try:
            asyncio.run(transfer.download_backup_plain(manual_path.name, {"confirm": True, "password": "wrong"}))
            raise AssertionError("legacy plain download with wrong password should fail")
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 422

        response = asyncio.run(transfer.download_backup_plain(
            manual_path.name,
            {"confirm": True, "password": "correct horse battery staple"}
        ))
        plain = json.loads(response.body.decode("utf-8"))
        assert plain["entries"][0]["title"] == "Before password change"


def main() -> None:
    tests = [
        test_manual_backup_uses_manual_dir_and_survives_auto_cleanup,
        test_legacy_root_backups_are_migrated_to_auto_dir,
        test_backup_list_reports_manual_and_auto_types,
        test_auto_backup_cleanup_uses_settings_retention,
        test_backup_list_includes_display_and_download_names,
        test_backup_downloads_encrypted_and_plain_with_confirmation,
        test_backup_summary_includes_current_vault_counts,
        test_plain_backup_download_requires_correct_legacy_password,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
