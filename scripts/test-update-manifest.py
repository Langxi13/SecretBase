from __future__ import annotations

import base64
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desktop.update import (  # noqa: E402
    LATEST_MANIFEST_URL,
    LATEST_SIGNATURE_URL,
    UPDATE_PUBLIC_KEYS,
    check_for_updates,
    verify_signed_manifest,
)
from desktop.updater import DesktopUpdateManager  # noqa: E402


class BytesResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        self.close()


class RoutingOpener:
    def __init__(self, routes: dict[str, bytes]) -> None:
        self.routes = routes

    def open(self, request, timeout: float):
        url = request.full_url
        if url not in self.routes:
            raise OSError(f"unexpected URL: {url}")
        return BytesResponse(self.routes[url])


def signed_manifest(
    private_key: Ed25519PrivateKey,
    *,
    version: str = "5.0.1",
    asset_bytes: bytes = b"windows-installer",
) -> tuple[bytes, bytes, str, str]:
    public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = hashlib.sha256(public).hexdigest()[:16]
    filename = f"SecretBase-v{version}-windows-x64-setup.exe"
    asset_url = f"https://github.com/Langxi13/SecretBase/releases/download/v{version}/{filename}"
    payload = {
        "schema_version": 1,
        "key_id": key_id,
        "channel": "stable",
        "version": version,
        "published_at": "2026-07-16T00:00:00Z",
        "release_url": f"https://github.com/Langxi13/SecretBase/releases/tag/v{version}",
        "notes": "更新测试",
        "assets": {
            "windows-x64-installer": {
                "filename": filename,
                "url": asset_url,
                "size": len(asset_bytes),
                "sha256": hashlib.sha256(asset_bytes).hexdigest(),
            },
            "macos-arm64-dmg": {
                "filename": f"SecretBase-v{version}-macos-arm64.dmg",
                "url": (
                    f"https://github.com/Langxi13/SecretBase/releases/download/v{version}/"
                    f"SecretBase-v{version}-macos-arm64.dmg"
                ),
                "size": 1,
                "sha256": "0" * 64,
            },
        },
    }
    manifest = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    signature = base64.b64encode(private_key.sign(manifest)) + b"\n"
    encoded_public = base64.b64encode(public).decode("ascii")
    return manifest, signature, encoded_public, asset_url


def test_signed_manifest_and_platform_selection() -> None:
    private_key = Ed25519PrivateKey.generate()
    manifest, signature, public, _asset_url = signed_manifest(private_key)
    key_id = json.loads(manifest)["key_id"]
    with patch.dict(UPDATE_PUBLIC_KEYS, {key_id: public}, clear=False):
        verified = verify_signed_manifest(manifest, signature)
        assert verified["version"] == "5.0.1"
        opener = RoutingOpener({LATEST_MANIFEST_URL: manifest, LATEST_SIGNATURE_URL: signature})
        windows = check_for_updates(
            "5.0.0",
            platform="windows",
            architecture="x64",
            package_type="installed",
            opener=opener,
        )
        assert windows["status"] == "available"
        assert windows["install_supported"] is True
        assert windows["asset"]["filename"].endswith("setup.exe")

        macos = check_for_updates(
            "5.0.0",
            platform="macos",
            architecture="arm64",
            package_type="installed",
            opener=opener,
        )
        assert macos["status"] == "available"
        assert macos["install_supported"] is False
        assert macos["manual_download_url"].endswith("macos-arm64.dmg")

        tampered = manifest.replace(b"5.0.1", b"5.0.2", 1)
        try:
            verify_signed_manifest(tampered, signature)
        except ValueError as error:
            assert "签名校验失败" in str(error)
        else:
            raise AssertionError("tampered update manifest must be rejected")


def test_desktop_update_download_and_install_handoff() -> None:
    private_key = Ed25519PrivateKey.generate()
    asset_bytes = b"verified-windows-installer"
    manifest, signature, public, asset_url = signed_manifest(private_key, asset_bytes=asset_bytes)
    key_id = json.loads(manifest)["key_id"]
    opener = RoutingOpener({
        LATEST_MANIFEST_URL: manifest,
        LATEST_SIGNATURE_URL: signature,
        asset_url: asset_bytes,
    })
    launched = []
    exited = threading.Event()
    with tempfile.TemporaryDirectory() as raw, patch.dict(
        UPDATE_PUBLIC_KEYS,
        {key_id: public},
        clear=False,
    ):
        root = Path(raw)
        settings = root / "settings.json"
        settings.write_text('{"desktop_update_auto_download":false}', encoding="utf-8")
        manager = DesktopUpdateManager(
            current_version="5.0.0",
            platform="windows",
            architecture="x64",
            package_type="installed",
            updates_dir=root / "updates",
            settings_path=settings,
            exit_callback=exited.set,
            opener=opener,
            process_launcher=lambda command, **kwargs: launched.append((command, kwargs)),
        )
        assert manager.check()["status"] == "available"
        manager.start_download()
        deadline = time.monotonic() + 3
        while manager.get_state()["status"] == "downloading" and time.monotonic() < deadline:
            time.sleep(0.02)
        assert manager.get_state()["status"] == "ready"
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            failed = manager.install()
        assert failed["status"] == "error"
        assert "无法准备或启动" in failed["message"]
        assert not launched
        assert manager.install()["status"] == "installing"
        assert launched and "/AUTOUPDATE=1" in launched[0][0]
        assert any(item.startswith("/LOG=") for item in launched[0][0])
        assert (root / "updates" / "pending-update.json").is_file()
        assert exited.wait(1)
        manager.shutdown()


def test_disabling_auto_check_cancels_scheduled_check() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        manager = DesktopUpdateManager(
            current_version="5.0.0",
            platform="windows",
            architecture="x64",
            package_type="installed",
            updates_dir=root / "updates",
            settings_path=root / "settings.json",
            exit_callback=lambda: None,
        )
        assert manager.start_background_check(delay=60) is True
        manager.set_preferences(False, False)
        assert manager.check(force=False)["status"] == "idle"
        manager.shutdown()


def test_release_manifest_generator() -> None:
    private_key = Ed25519PrivateKey.generate()
    public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = hashlib.sha256(public).hexdigest()[:16]
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        assets = root / "assets"
        output = root / "output"
        assets.mkdir()
        private_path = root / "private.pem"
        private_path.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        for filename in (
            "SecretBase-v5.0.0-windows-x64-setup.exe",
            "SecretBase-v5.0.0-macos-arm64.dmg",
            "SecretBase-v5.0.0-android-universal.apk",
        ):
            (assets / filename).write_bytes(filename.encode("ascii"))
        (assets / "ANDROID-METADATA.json").write_text(
            json.dumps({
                "package_id": "io.github.langxi13.secretbase",
                "version_name": "5.0.0",
                "version_code": 5000000,
                "signer_sha256": "a" * 64,
            }),
            encoding="utf-8",
        )
        subprocess.run(
            [
                sys.executable,
                "scripts/generate-update-manifest.py",
                "--version",
                "5.0.0",
                "--assets-dir",
                str(assets),
                "--output-dir",
                str(output),
                "--private-key-file",
                str(private_path),
                "--expected-key-id",
                key_id,
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        manifest = (output / "secretbase-update-v1.json").read_bytes()
        signature = (output / "secretbase-update-v1.json.sig").read_bytes()
        with patch.dict(
            UPDATE_PUBLIC_KEYS,
            {key_id: base64.b64encode(public).decode("ascii")},
            clear=False,
        ):
            payload = verify_signed_manifest(manifest, signature)
        assert payload["assets"]["android-universal"]["version_code"] == 5000000


def main() -> int:
    for test in (
        test_signed_manifest_and_platform_selection,
        test_desktop_update_download_and_install_handoff,
        test_disabling_auto_check_cancels_scheduled_check,
        test_release_manifest_generator,
    ):
        test()
    print("PASS update manifest and desktop updater tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
