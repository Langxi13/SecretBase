"""Strict WebDAV transport used by encrypted SecretBase synchronization."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from urllib.parse import quote, unquote, urlsplit

import httpx

from sync_webdav_capabilities import WebDavCapabilityMixin
from sync_webdav_common import (
    MAX_PROPFIND_BYTES,
    MAX_REMOTE_BYTES,
    RemoteChild,
    RemoteObject,
    SYNC_ROOT,
    SYNC_ROOT_V2,
    WebDavError,
    normalize_webdav_url,
    strong_etag as _strong_etag,
)

REQUEST_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=10.0)
MAX_RETRIES = 3
RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}


class WebDavClient(WebDavCapabilityMixin):
    def __init__(self, base_url: str, username: str, password: str, *, allow_loopback_http: bool = False):
        self.base_url = normalize_webdav_url(base_url, allow_loopback_http=allow_loopback_http)
        username = str(username or "").strip()
        password = str(password or "")
        if not username or not password:
            raise WebDavError("WEBDAV_CREDENTIALS_REQUIRED", "请输入 WebDAV 用户名和密码", status_code=422)
        self._client = httpx.Client(
            auth=httpx.BasicAuth(username, password),
            timeout=REQUEST_TIMEOUT,
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "SecretBase-WebDAV-Sync/1"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def _url(self, *segments: str) -> str:
        suffix = "/".join(quote(str(segment), safe="") for segment in segments if str(segment))
        return f"{self.base_url.rstrip('/')}/{suffix}" if suffix else self.base_url

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.request(method, url, **kwargs)
            except httpx.TimeoutException as error:
                if attempt + 1 < MAX_RETRIES:
                    time.sleep(0.25 * (2 ** attempt))
                    continue
                raise WebDavError("WEBDAV_TIMEOUT", "WebDAV 请求超时，请检查网络后重试") from error
            except httpx.TransportError as error:
                if attempt + 1 < MAX_RETRIES:
                    time.sleep(0.25 * (2 ** attempt))
                    continue
                raise WebDavError("WEBDAV_UNREACHABLE", "无法连接 WebDAV 服务") from error
            if response.status_code in RETRYABLE_STATUSES and attempt + 1 < MAX_RETRIES:
                time.sleep(self._retry_delay(response, attempt))
                continue
            if 300 <= response.status_code < 400:
                raise WebDavError("WEBDAV_REDIRECT_REJECTED", "WebDAV 服务返回了不受信任的重定向")
            if response.status_code in {401, 403}:
                raise WebDavError("WEBDAV_AUTH_FAILED", "WebDAV 用户名、密码或目录权限无效", status_code=401)
            return response
        raise WebDavError("WEBDAV_UNREACHABLE", "无法连接 WebDAV 服务")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        header = str(response.headers.get("Retry-After", "")).strip()
        try:
            return min(5.0, max(0.0, float(header)))
        except ValueError:
            return min(5.0, 0.25 * (2 ** attempt))

    def _validate_stream_response(self, response: httpx.Response) -> None:
        if 300 <= response.status_code < 400:
            raise WebDavError("WEBDAV_REDIRECT_REJECTED", "WebDAV 服务返回了不受信任的重定向")
        if response.status_code in {401, 403}:
            raise WebDavError("WEBDAV_AUTH_FAILED", "WebDAV 用户名、密码或目录权限无效", status_code=401)

    def ensure_layout(self, vault_id: str) -> None:
        for segments in ((SYNC_ROOT,), (SYNC_ROOT, vault_id), (SYNC_ROOT, vault_id, "snapshots")):
            response = self._request("MKCOL", self._url(*segments))
            if response.status_code not in {201, 405}:
                raise WebDavError("WEBDAV_MKCOL_FAILED", f"WebDAV 无法创建同步目录：HTTP {response.status_code}")

    def get(
        self,
        *segments: str,
        optional: bool = False,
        require_etag: bool = True,
    ) -> RemoteObject | None:
        url = self._url(*segments)
        for attempt in range(MAX_RETRIES):
            try:
                with self._client.stream("GET", url) as response:
                    if response.status_code in RETRYABLE_STATUSES and attempt + 1 < MAX_RETRIES:
                        time.sleep(self._retry_delay(response, attempt))
                        continue
                    self._validate_stream_response(response)
                    if optional and response.status_code == 404:
                        return None
                    if response.status_code != 200:
                        raise WebDavError("WEBDAV_READ_FAILED", f"WebDAV 读取失败：HTTP {response.status_code}")
                    etag_header = response.headers.get("ETag")
                    etag = _strong_etag(etag_header) if require_etag else str(etag_header or "")
                    try:
                        declared_length = int(response.headers.get("Content-Length", "0"))
                    except ValueError:
                        declared_length = 0
                    if declared_length > MAX_REMOTE_BYTES:
                        raise WebDavError("WEBDAV_OBJECT_TOO_LARGE", "WebDAV 同步对象过大")
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_REMOTE_BYTES:
                            raise WebDavError("WEBDAV_OBJECT_TOO_LARGE", "WebDAV 同步对象过大")
                    return RemoteObject(bytes(content), etag)
            except httpx.TimeoutException as error:
                if attempt + 1 < MAX_RETRIES:
                    time.sleep(0.25 * (2 ** attempt))
                    continue
                raise WebDavError("WEBDAV_TIMEOUT", "WebDAV 请求超时，请检查网络后重试") from error
            except httpx.TransportError as error:
                if attempt + 1 < MAX_RETRIES:
                    time.sleep(0.25 * (2 ** attempt))
                    continue
                raise WebDavError("WEBDAV_UNREACHABLE", "无法连接 WebDAV 服务") from error
        raise WebDavError("WEBDAV_UNREACHABLE", "无法连接 WebDAV 服务")

    def put(
        self,
        content: bytes,
        *segments: str,
        if_match: str | None = None,
        if_none_match: bool = False,
        require_etag: bool = True,
    ) -> str:
        if len(content) > MAX_REMOTE_BYTES:
            raise WebDavError("WEBDAV_OBJECT_TOO_LARGE", "WebDAV 同步对象过大")
        headers = {"Content-Type": "application/octet-stream"}
        if if_match:
            headers["If-Match"] = if_match
        if if_none_match:
            headers["If-None-Match"] = "*"
        response = self._request("PUT", self._url(*segments), content=content, headers=headers)
        if response.status_code == 412:
            raise WebDavError("WEBDAV_PRECONDITION_FAILED", "远端版本已经变化", status_code=409)
        if response.status_code not in {200, 201, 204}:
            raise WebDavError("WEBDAV_WRITE_FAILED", f"WebDAV 写入失败：HTTP {response.status_code}")
        etag = response.headers.get("ETag")
        if etag:
            return _strong_etag(etag)
        if not require_etag:
            return ""
        stored = self.get(*segments)
        if stored is None:
            raise WebDavError("WEBDAV_WRITE_FAILED", "WebDAV 写入后无法读取对象")
        return stored.etag

    def put_unconditional(self, content: bytes, *segments: str) -> None:
        """写入 V2 唯一路径，不发送条件头，也不要求服务返回 ETag。"""
        self.put(content, *segments, require_etag=False)

    def delete(self, *segments: str, optional: bool = True, if_match: str | None = None) -> None:
        headers = {"If-Match": if_match} if if_match else None
        response = self._request("DELETE", self._url(*segments), headers=headers)
        if optional and response.status_code == 404:
            return
        if response.status_code == 412:
            raise WebDavError("WEBDAV_PRECONDITION_FAILED", "远端版本已经变化", status_code=409)
        if response.status_code not in {200, 204}:
            raise WebDavError("WEBDAV_DELETE_FAILED", f"WebDAV 删除失败：HTTP {response.status_code}")

    def list_children(self, *segments: str, optional: bool = False) -> list[RemoteChild]:
        """列出 WebDAV 集合的直接子项，不依赖 ETag。"""
        url = self._url(*segments)
        headers = {"Depth": "1", "Content-Type": "application/xml; charset=utf-8"}
        body = b"<?xml version=\"1.0\" encoding=\"utf-8\"?><propfind xmlns=\"DAV:\"><prop><resourcetype/><getcontentlength/></prop></propfind>"
        response = self._request("PROPFIND", url, content=body, headers=headers)
        if optional and response.status_code == 404:
            return []
        if response.status_code not in {200, 207}:
            raise WebDavError("WEBDAV_LIST_FAILED", f"WebDAV 目录读取失败：HTTP {response.status_code}")
        raw = response.content
        if len(raw) > MAX_PROPFIND_BYTES:
            raise WebDavError("WEBDAV_DIRECTORY_TOO_LARGE", "WebDAV 目录响应过大")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as error:
            raise WebDavError("WEBDAV_LIST_INVALID", "WebDAV 目录响应格式无效") from error

        requested_path = urlsplit(url).path.rstrip("/") or "/"
        result: dict[str, RemoteChild] = {}
        for response_node in root.iter():
            if response_node.tag.rsplit("}", 1)[-1] != "response":
                continue
            href = ""
            is_collection = False
            content_length = 0
            for child in response_node.iter():
                local = child.tag.rsplit("}", 1)[-1]
                if local == "href" and child.text:
                    href = child.text.strip()
                elif local == "collection":
                    is_collection = True
                elif local == "getcontentlength" and child.text:
                    try:
                        content_length = max(0, int(child.text.strip()))
                    except ValueError:
                        content_length = 0
            if not href:
                continue
            parsed = urlsplit(href)
            path = unquote(parsed.path or href).rstrip("/") or "/"
            if path == requested_path:
                continue
            prefix = requested_path.rstrip("/") + "/"
            if not path.startswith(prefix):
                continue
            relative = path[len(prefix):]
            if "/" in relative or not relative:
                continue
            result[relative] = RemoteChild(relative, is_collection, content_length)
        return sorted(result.values(), key=lambda item: item.name)
