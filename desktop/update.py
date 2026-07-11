from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse


LATEST_RELEASE_API = "https://api.github.com/repos/Langxi13/SecretBase/releases/latest"
RELEASE_PAGE_PREFIX = "https://github.com/Langxi13/SecretBase/releases/tag/"
VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(value: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(str(value or "").strip())
    if not match:
        raise ValueError("版本号格式无效")
    return tuple(int(item) for item in match.groups())


def validate_release_url(value: str) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise ValueError("更新地址不是受信任的 GitHub 页面")
    if not url.startswith(RELEASE_PAGE_PREFIX):
        raise ValueError("更新地址不属于 SecretBase Release")
    return url


def check_for_updates(
    current_version: str,
    *,
    opener=None,
    timeout: float = 8.0,
) -> dict[str, str | bool | None]:
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"SecretBase/{current_version}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    client = opener or urllib.request.build_opener()
    try:
        with client.open(request, timeout=timeout) as response:
            payload = json.loads(response.read(512 * 1024).decode("utf-8"))
        if payload.get("draft") or payload.get("prerelease"):
            raise ValueError("GitHub 返回的不是正式版本")
        latest_tag = str(payload.get("tag_name") or "")
        latest_version = latest_tag.removeprefix("v")
        release_url = validate_release_url(str(payload.get("html_url") or ""))
        available = parse_version(latest_version) > parse_version(current_version)
        return {
            "status": "available" if available else "up_to_date",
            "available": available,
            "current_version": current_version,
            "latest_version": latest_version,
            "release_url": release_url,
            "published_at": payload.get("published_at"),
        }
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as error:
        return {
            "status": "error",
            "available": False,
            "current_version": current_version,
            "latest_version": None,
            "release_url": None,
            "published_at": None,
            "message": f"无法检查更新：{error}",
        }
