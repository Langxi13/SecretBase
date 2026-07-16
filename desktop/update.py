from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


REPOSITORY = "Langxi13/SecretBase"
LATEST_MANIFEST_URL = (
    f"https://github.com/{REPOSITORY}/releases/latest/download/secretbase-update-v1.json"
)
LATEST_SIGNATURE_URL = f"{LATEST_MANIFEST_URL}.sig"
RELEASE_PAGE_PREFIX = f"https://github.com/{REPOSITORY}/releases/tag/"
RELEASE_DOWNLOAD_PREFIX = f"https://github.com/{REPOSITORY}/releases/download/"
UPDATE_PUBLIC_KEYS = {
    "1c9180b8f11c8c43": "BAED+Er+yGF73nPHdj2SlkxkC1E6g5Rnw0muCqw77B4=",
}
VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ASSET_KEYS = {
    ("windows", "x64", "installed"): "windows-x64-installer",
    ("macos", "arm64", "installed"): "macos-arm64-dmg",
}
MAX_MANIFEST_BYTES = 512 * 1024
MAX_SIGNATURE_BYTES = 4096


@dataclass(frozen=True)
class UpdateTarget:
    platform: str
    architecture: str
    package_type: str


class UpdateManifestError(ValueError):
    pass


def parse_version(value: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(str(value or "").strip())
    if not match:
        raise UpdateManifestError("版本号格式无效")
    return tuple(int(item) for item in match.groups())


def validate_release_url(value: str) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise UpdateManifestError("更新地址不是受信任的 GitHub 页面")
    if not url.startswith(RELEASE_PAGE_PREFIX):
        raise UpdateManifestError("更新地址不属于 SecretBase Release")
    return url


def validate_asset_url(value: str) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise UpdateManifestError("更新文件地址不是受信任的 GitHub 地址")
    if not url.startswith(RELEASE_DOWNLOAD_PREFIX):
        raise UpdateManifestError("更新文件不属于 SecretBase Release")
    return url


def _decode_signature(signature_bytes: bytes) -> bytes:
    try:
        signature = base64.b64decode(signature_bytes.strip(), validate=True)
    except (ValueError, TypeError) as error:
        raise UpdateManifestError("更新清单签名格式无效") from error
    if len(signature) != 64:
        raise UpdateManifestError("更新清单签名长度无效")
    return signature


def verify_signed_manifest(manifest_bytes: bytes, signature_bytes: bytes) -> dict[str, Any]:
    if not manifest_bytes or len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise UpdateManifestError("更新清单大小无效")
    if not signature_bytes or len(signature_bytes) > MAX_SIGNATURE_BYTES:
        raise UpdateManifestError("更新清单签名大小无效")
    try:
        payload = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpdateManifestError("更新清单不是有效 JSON") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise UpdateManifestError("不支持的更新清单版本")

    key_id = str(payload.get("key_id") or "")
    encoded_key = UPDATE_PUBLIC_KEYS.get(key_id)
    if not encoded_key:
        raise UpdateManifestError("更新清单使用了未知签名密钥")
    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded_key))
    try:
        public_key.verify(_decode_signature(signature_bytes), manifest_bytes)
    except InvalidSignature as error:
        raise UpdateManifestError("更新清单签名校验失败") from error

    if payload.get("channel") != "stable":
        raise UpdateManifestError("更新清单不是稳定通道")
    version = str(payload.get("version") or "")
    parse_version(version)
    release_url = validate_release_url(str(payload.get("release_url") or ""))
    if not release_url.endswith(f"/v{version}"):
        raise UpdateManifestError("更新版本与 Release 地址不一致")
    if not isinstance(payload.get("assets"), dict):
        raise UpdateManifestError("更新清单缺少平台文件")
    return payload


def validate_asset(asset: Any, *, expected_version: str) -> dict[str, Any]:
    if not isinstance(asset, dict):
        raise UpdateManifestError("更新文件信息无效")
    filename = str(asset.get("filename") or "")
    if not filename or filename != filename.split("/")[-1] or filename != filename.split("\\")[-1]:
        raise UpdateManifestError("更新文件名无效")
    url = validate_asset_url(str(asset.get("url") or ""))
    if not url.endswith(f"/{filename}") or f"/v{expected_version}/" not in url:
        raise UpdateManifestError("更新文件地址与版本不一致")
    sha256 = str(asset.get("sha256") or "").lower()
    if not SHA256_PATTERN.fullmatch(sha256):
        raise UpdateManifestError("更新文件哈希无效")
    size = asset.get("size")
    if type(size) is not int or size <= 0:
        raise UpdateManifestError("更新文件大小无效")
    return {
        **asset,
        "filename": filename,
        "url": url,
        "sha256": sha256,
        "size": size,
    }


def select_desktop_asset(payload: dict[str, Any], target: UpdateTarget) -> dict[str, Any] | None:
    asset_key = ASSET_KEYS.get((target.platform, target.architecture, target.package_type))
    if asset_key is None:
        return None
    asset = payload["assets"].get(asset_key)
    return validate_asset(asset, expected_version=str(payload["version"]))


def _read_url(client, url: str, *, timeout: float, limit: int) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": "SecretBase-Updater/1",
        },
    )
    with client.open(request, timeout=timeout) as response:
        content = response.read(limit + 1)
    if len(content) > limit:
        raise UpdateManifestError("更新响应超过大小限制")
    return content


def fetch_signed_manifest(*, opener=None, timeout: float = 8.0) -> dict[str, Any]:
    client = opener or urllib.request.build_opener()
    manifest = _read_url(client, LATEST_MANIFEST_URL, timeout=timeout, limit=MAX_MANIFEST_BYTES)
    signature = _read_url(client, LATEST_SIGNATURE_URL, timeout=timeout, limit=MAX_SIGNATURE_BYTES)
    return verify_signed_manifest(manifest, signature)


def check_for_updates(
    current_version: str,
    *,
    platform: str = "windows",
    architecture: str = "x64",
    package_type: str = "installed",
    opener=None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    try:
        payload = fetch_signed_manifest(opener=opener, timeout=timeout)
        latest_version = str(payload["version"])
        available = parse_version(latest_version) > parse_version(current_version)
        asset = select_desktop_asset(
            payload,
            UpdateTarget(platform=platform, architecture=architecture, package_type=package_type),
        )
        install_supported = (
            available
            and asset is not None
            and platform == "windows"
            and package_type == "installed"
        )
        return {
            "status": "available" if available else "up_to_date",
            "available": available,
            "current_version": current_version,
            "latest_version": latest_version,
            "release_url": payload["release_url"],
            "published_at": payload.get("published_at"),
            "notes": str(payload.get("notes") or ""),
            "install_supported": install_supported,
            "manual_download_url": asset["url"] if available and asset is not None else None,
            "asset": asset if install_supported else None,
        }
    except (
        OSError,
        UpdateManifestError,
        urllib.error.URLError,
    ) as error:
        return {
            "status": "error",
            "available": False,
            "current_version": current_version,
            "latest_version": None,
            "release_url": None,
            "published_at": None,
            "notes": "",
            "install_supported": False,
            "manual_download_url": None,
            "asset": None,
            "message": f"无法检查更新：{error}",
        }
