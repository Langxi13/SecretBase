from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import storage  # noqa: E402
from models import Entry  # noqa: E402
from routes import transfer  # noqa: E402


def reset_storage(tmpdir: Path, max_backups: int = 2) -> None:
    storage.lock_vault()
    data_dir = tmpdir / "data"
    backup_dir = data_dir / "backups"
    data_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    storage.VAULT_PATH = str(data_dir / "secretbase.enc")
    storage.BACKUP_DIR = str(backup_dir)
    storage.MAX_BACKUPS = max_backups
    transfer.BACKUP_DIR = str(backup_dir)

    assert storage.init_vault("correct horse battery staple")


def write_entry(title: str) -> None:
    vault = storage.get_vault_data()
    vault.entries.append(Entry(title=title))
    storage.save_vault_data(vault)


def test_manual_backup_uses_manual_dir_and_survives_auto_cleanup() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmpdir = Path(raw)
        reset_storage(tmpdir, max_backups=2)

        manual_path = storage.create_backup()
        assert manual_path.parent.name == "manual"

        for index in range(5):
            write_entry(f"Entry {index}")

        auto_backups = sorted((tmpdir / "data" / "backups" / "auto").glob("*.bak"))
        assert len(auto_backups) <= 2
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


def main() -> None:
    tests = [
        test_manual_backup_uses_manual_dir_and_survives_auto_cleanup,
        test_legacy_root_backups_are_migrated_to_auto_dir,
        test_backup_list_reports_manual_and_auto_types,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
