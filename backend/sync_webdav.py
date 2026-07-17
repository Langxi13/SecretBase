"""Strict WebDAV transport used by encrypted SecretBase synchronization."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from urllib.parse import quote, urlsplit, urlunsplit

import httpx


SYNC_ROOT = "secretbase-sync-v1"
REQUEST_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=10.0)
MAX_REMOTE_BYTES = 64 * 1024 * 1024


class WebDavError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class RemoteObject:
    content: bytes
    etag: str


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


def _strong_etag(value: str | None) -> str:
    etag = str(value or "").strip()
    opaque = etag[1:-1] if len(etag) >= 2 and etag[0] == etag[-1] == '"' else None
    if (
        opaque is None
        or '"' in opaque
        or any(ord(character) < 0x21 or ord(character) == 0x7F for character in opaque)
    ):
        raise WebDavError("WEBDAV_ETAG_UNSUPPORTED", "WebDAV 服务未提供稳定的强 ETag")
    return etag


class WebDavClient:
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
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.TimeoutException as error:
            raise WebDavError("WEBDAV_TIMEOUT", "WebDAV 请求超时，请检查网络后重试") from error
        except httpx.TransportError as error:
            raise WebDavError("WEBDAV_UNREACHABLE", "无法连接 WebDAV 服务") from error
        if 300 <= response.status_code < 400:
            raise WebDavError("WEBDAV_REDIRECT_REJECTED", "WebDAV 服务返回了不受信任的重定向")
        if response.status_code in {401, 403}:
            raise WebDavError("WEBDAV_AUTH_FAILED", "WebDAV 用户名、密码或目录权限无效", status_code=401)
        return response

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

    def get(self, *segments: str, optional: bool = False) -> RemoteObject | None:
        try:
            with self._client.stream("GET", self._url(*segments)) as response:
                self._validate_stream_response(response)
                if optional and response.status_code == 404:
                    return None
                if response.status_code != 200:
                    raise WebDavError("WEBDAV_READ_FAILED", f"WebDAV 读取失败：HTTP {response.status_code}")
                etag = _strong_etag(response.headers.get("ETag"))
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
            raise WebDavError("WEBDAV_TIMEOUT", "WebDAV 请求超时，请检查网络后重试") from error
        except httpx.TransportError as error:
            raise WebDavError("WEBDAV_UNREACHABLE", "无法连接 WebDAV 服务") from error

    def put(
        self,
        content: bytes,
        *segments: str,
        if_match: str | None = None,
        if_none_match: bool = False,
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
        stored = self.get(*segments)
        if stored is None:
            raise WebDavError("WEBDAV_WRITE_FAILED", "WebDAV 写入后无法读取对象")
        return stored.etag

    def delete(self, *segments: str, optional: bool = True, if_match: str | None = None) -> None:
        headers = {"If-Match": if_match} if if_match else None
        response = self._request("DELETE", self._url(*segments), headers=headers)
        if optional and response.status_code == 404:
            return
        if response.status_code == 412:
            raise WebDavError("WEBDAV_PRECONDITION_FAILED", "远端版本已经变化", status_code=409)
        if response.status_code not in {200, 204}:
            raise WebDavError("WEBDAV_DELETE_FAILED", f"WebDAV 删除失败：HTTP {response.status_code}")

    def head_path(self, vault_id: str) -> tuple[str, ...]:
        return SYNC_ROOT, vault_id, "head.sbh"

    def snapshot_path(self, vault_id: str, snapshot_id: str) -> tuple[str, ...]:
        return SYNC_ROOT, vault_id, "snapshots", f"{snapshot_id}.sbs"

    def test_capabilities(self) -> dict:
        probe_vault = str(uuid.uuid4())
        probe_name = f"probe-{uuid.uuid4()}.bin"
        self.ensure_layout(probe_vault)
        path = self.snapshot_path(probe_vault, probe_name.removesuffix(".bin"))
        try:
            first_etag = self.put(b"secretbase-webdav-probe-v1", *path, if_none_match=True)
            stored = self.get(*path)
            if stored is None or stored.content != b"secretbase-webdav-probe-v1" or stored.etag != first_etag:
                raise WebDavError("WEBDAV_CAPABILITY_FAILED", "WebDAV 读写一致性检查失败")
            try:
                self.put(b"must-not-overwrite", *path, if_none_match=True)
            except WebDavError as error:
                if error.code != "WEBDAV_PRECONDITION_FAILED":
                    raise
            else:
                raise WebDavError("WEBDAV_CONDITIONAL_WRITE_UNSUPPORTED", "WebDAV 未正确执行条件写入")
            replacement_etag = self.put(b"secretbase-webdav-probe-v2", *path, if_match=first_etag)
            try:
                self.put(b"must-not-overwrite-v2", *path, if_match=first_etag)
            except WebDavError as error:
                if error.code != "WEBDAV_PRECONDITION_FAILED":
                    raise
            else:
                raise WebDavError("WEBDAV_CONDITIONAL_WRITE_UNSUPPORTED", "WebDAV 未拒绝过期 ETag 写入")
            try:
                self.delete(*path, optional=False, if_match=first_etag)
            except WebDavError as error:
                if error.code != "WEBDAV_PRECONDITION_FAILED":
                    raise
            else:
                raise WebDavError("WEBDAV_CONDITIONAL_DELETE_UNSUPPORTED", "WebDAV 未拒绝过期 ETag 删除")
            return {
                "conditional_write": True,
                "conditional_delete": True,
                "strong_etag": bool(replacement_etag),
            }
        finally:
            try:
                self.delete(*path)
            except WebDavError:
                pass
            for collection in (
                (SYNC_ROOT, probe_vault, "snapshots"),
                (SYNC_ROOT, probe_vault),
            ):
                try:
                    self.delete(*collection)
                except WebDavError:
                    pass
