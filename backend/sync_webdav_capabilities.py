"""V1/V2 WebDAV layout and capability probes."""

from __future__ import annotations

import uuid

from sync_webdav_common import SYNC_ROOT, SYNC_ROOT_V2, WebDavError


class WebDavCapabilityMixin:
    def head_path(self, vault_id: str) -> tuple[str, ...]:
        return SYNC_ROOT, vault_id, "head.sbh"

    def snapshot_path(self, vault_id: str, snapshot_id: str) -> tuple[str, ...]:
        return SYNC_ROOT, vault_id, "snapshots", f"{snapshot_id}.sbs"

    def ensure_v2_layout(self, vault_id: str, space_id: str, device_id: str | None = None) -> None:
        paths = (
            (SYNC_ROOT_V2,),
            (SYNC_ROOT_V2, vault_id),
            (SYNC_ROOT_V2, vault_id, space_id),
            (SYNC_ROOT_V2, vault_id, space_id, "snapshots"),
        )
        if device_id:
            paths += ((SYNC_ROOT_V2, vault_id, space_id, "snapshots", device_id),)
        for segments in paths:
            response = self._request("MKCOL", self._url(*segments))
            if response.status_code not in {201, 405}:
                raise WebDavError("WEBDAV_MKCOL_FAILED", f"WebDAV 无法创建同步目录：HTTP {response.status_code}")

    def v2_snapshots_path(self, vault_id: str, space_id: str) -> tuple[str, ...]:
        return SYNC_ROOT_V2, vault_id, space_id, "snapshots"

    def v2_device_path(self, vault_id: str, space_id: str, device_id: str) -> tuple[str, ...]:
        return (*self.v2_snapshots_path(vault_id, space_id), device_id)

    def v2_snapshot_path(
        self,
        vault_id: str,
        space_id: str,
        device_id: str,
        generation: int,
        snapshot_id: str,
    ) -> tuple[str, ...]:
        return (*self.v2_device_path(vault_id, space_id, device_id), f"{generation}-{snapshot_id}.sbs")

    def test_basic_capabilities(self) -> dict:
        """测试 V2 所需的基础 WebDAV 能力，不要求 ETag 或条件写入。"""
        probe_vault = str(uuid.uuid4())
        probe_space = str(uuid.uuid4())
        probe_device = str(uuid.uuid4())
        probe_snapshot = str(uuid.uuid4())
        self.ensure_v2_layout(probe_vault, probe_space, probe_device)
        path = self.v2_snapshot_path(probe_vault, probe_space, probe_device, 1, probe_snapshot)
        content = b"secretbase-webdav-probe-v2"
        try:
            self.put_unconditional(content, *path)
            stored = self.get(*path, require_etag=False)
            if stored is None or stored.content != content:
                raise WebDavError("WEBDAV_CAPABILITY_FAILED", "WebDAV 读写一致性检查失败")
            children = self.list_children(*self.v2_snapshots_path(probe_vault, probe_space))
            if not any(item.name == probe_device and item.is_collection for item in children):
                raise WebDavError("WEBDAV_CAPABILITY_FAILED", "WebDAV PROPFIND 目录发现失败")
            return {
                "basic_write": True,
                "propfind": True,
                "conditional_write": False,
                "strong_etag": False,
            }
        finally:
            self._cleanup_probe(path, (
                self.v2_device_path(probe_vault, probe_space, probe_device),
                self.v2_snapshots_path(probe_vault, probe_space),
                (SYNC_ROOT_V2, probe_vault, probe_space),
                (SYNC_ROOT_V2, probe_vault),
            ))

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
            self._expect_precondition(
                lambda: self.put(b"must-not-overwrite", *path, if_none_match=True),
                "WebDAV 未正确执行条件写入",
            )
            replacement_etag = self.put(b"secretbase-webdav-probe-v2", *path, if_match=first_etag)
            self._expect_precondition(
                lambda: self.put(b"must-not-overwrite-v2", *path, if_match=first_etag),
                "WebDAV 未拒绝过期 ETag 写入",
            )
            self._expect_precondition(
                lambda: self.delete(*path, optional=False, if_match=first_etag),
                "WebDAV 未拒绝过期 ETag 删除",
                code="WEBDAV_CONDITIONAL_DELETE_UNSUPPORTED",
            )
            return {
                "conditional_write": True,
                "conditional_delete": True,
                "strong_etag": bool(replacement_etag),
            }
        finally:
            self._cleanup_probe(path, (
                (SYNC_ROOT, probe_vault, "snapshots"),
                (SYNC_ROOT, probe_vault),
            ))

    @staticmethod
    def _expect_precondition(
        operation,
        message: str,
        *,
        code: str = "WEBDAV_CONDITIONAL_WRITE_UNSUPPORTED",
    ) -> None:
        try:
            operation()
        except WebDavError as error:
            if error.code != "WEBDAV_PRECONDITION_FAILED":
                raise
            return
        raise WebDavError(code, message)

    def _cleanup_probe(self, path: tuple[str, ...], collections: tuple[tuple[str, ...], ...]) -> None:
        try:
            self.delete(*path)
        except WebDavError:
            pass
        for collection in collections:
            try:
                self.delete(*collection)
            except WebDavError:
                pass
