"""Shared WebDAV validation, limits, and response value objects."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


SYNC_ROOT = "secretbase-sync-v1"
SYNC_ROOT_V2 = "secretbase-sync-v2"
MAX_REMOTE_BYTES = 64 * 1024 * 1024
MAX_PROPFIND_BYTES = 4 * 1024 * 1024


class WebDavError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class RemoteObject:
    content: bytes
    etag: str = ""


@dataclass(frozen=True)
class RemoteChild:
    name: str
    is_collection: bool
    content_length: int = 0


def normalize_webdav_url(value: str, *, allow_loopback_http: bool = False) -> str:
    raw = str(value or "").strip()
    try:
        parsed = urlsplit(raw)
    except ValueError as error:
        raise WebDavError("INVALID_WEBDAV_URL", "WebDAV 地址无效", status_code=422) from error
    hostname = (parsed.hostname or "").lower()
    loopback = hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (allow_loopback_http and parsed.scheme == "http" and loopback):
        raise WebDavError("INSECURE_WEBDAV_URL", "WebDAV 必须使用 HTTPS", status_code=422)
    if not hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise WebDavError("INVALID_WEBDAV_URL", "WebDAV 地址不能包含账号、查询参数或片段", status_code=422)
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def strong_etag(value: str | None) -> str:
    etag = str(value or "").strip()
    opaque = etag[1:-1] if len(etag) >= 2 and etag[0] == etag[-1] == '"' else None
    if (
        opaque is None
        or '"' in opaque
        or any(ord(character) < 0x21 or ord(character) == 0x7F for character in opaque)
    ):
        raise WebDavError("WEBDAV_ETAG_UNSUPPORTED", "WebDAV 服务未提供稳定的强 ETag")
    return etag
