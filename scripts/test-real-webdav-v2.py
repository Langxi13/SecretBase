"""在用户指定的专用 WebDAV 根目录执行一次无明文数据的 V2 兼容性探测。

脚本只使用随机 Vault/space/device UUID 和合成文档，不读取 SecretBase 本机 Vault，
也不会打印或保存 WebDAV 地址、用户名和应用密码。建议在专用目录上交互运行。
"""

from __future__ import annotations

import getpass
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sync_v2_remote import SyncV2Repository
from sync_webdav import WebDavClient, WebDavError, normalize_webdav_url


def _input(name: str, *, secret: bool = False) -> str:
    value = (getpass.getpass if secret else input)(f"{name}: ").strip()
    if not value:
        raise RuntimeError(f"{name} 不能为空")
    return value


def _document(vault_id: str, title: str) -> dict:
    return {
        "version": "1.0",
        "created_at": "2026-01-01T00:00:00Z",
        "app_name": "SecretBase V2 probe",
        "vault_id": vault_id,
        "entries": [{"id": "probe-entry", "title": title, "fields": []}],
        "deleted_entries": [],
        "tags_meta": {},
        "groups_meta": {},
    }


def main() -> int:
    base_url = os.environ.get("SECRETBASE_TEST_WEBDAV_URL") or _input("WebDAV 地址")
    username = os.environ.get("SECRETBASE_TEST_WEBDAV_USERNAME") or _input("WebDAV 用户名")
    password = os.environ.get("SECRETBASE_TEST_WEBDAV_PASSWORD") or _input("WebDAV 应用密码", secret=True)
    base_url = normalize_webdav_url(base_url)

    vault_id = str(uuid.uuid4())
    space_id = str(uuid.uuid4())
    device_a = str(uuid.uuid4())
    device_b = str(uuid.uuid4())
    key = os.urandom(32)
    repository = None
    cleanup_error: WebDavError | None = None
    try:
        with WebDavClient(base_url, username, password) as webdav:
            capabilities = webdav.test_basic_capabilities()
            if not capabilities.get("basic_write") or not capabilities.get("propfind"):
                raise RuntimeError("WebDAV 未提供 V2 所需的基础能力")
            repository = SyncV2Repository(
                webdav,
                vault_id=vault_id,
                space_id=space_id,
                sync_key=key,
            )
            try:
                repository.ensure_layout(device_a)
                root = repository.publish(
                    _document(vault_id, "probe-root"),
                    parents=[],
                    generation=1,
                    device_id=device_a,
                    device_name="probe-a",
                )
                repository.ensure_layout(device_b)
                branch_a = repository.publish(
                    _document(vault_id, "probe-a"),
                    parents=[root.snapshot_id],
                    generation=2,
                    device_id=device_a,
                    device_name="probe-a",
                )
                branch_b = repository.publish(
                    _document(vault_id, "probe-b"),
                    parents=[root.snapshot_id],
                    generation=2,
                    device_id=device_b,
                    device_name="probe-b",
                )
                graph = repository.discover()
                if set(graph.frontier) != {branch_a.snapshot_id, branch_b.snapshot_id}:
                    raise RuntimeError("PROPFIND 发现的并发 frontier 不完整")
                merged = repository.publish(
                    _document(vault_id, "probe-merged"),
                    parents=list(graph.frontier),
                    generation=graph.max_generation + 1,
                    device_id=device_a,
                    device_name="probe-a",
                )
                verified = repository.discover()
                if verified.frontier != (merged.snapshot_id,):
                    raise RuntimeError("上传后的 DAG frontier 校验失败")
                if not verified.get(merged.snapshot_id).digest:
                    raise RuntimeError("快照密文摘要为空")
            finally:
                try:
                    repository.delete_remote()
                except WebDavError as error:
                    cleanup_error = error
        if cleanup_error is not None:
            raise RuntimeError(f"真实 WebDAV 测试对象清理失败：{cleanup_error}")
        print("PASS 真实 WebDAV V2 兼容性探测（仅合成数据）")
        return 0
    except (WebDavError, RuntimeError, ValueError) as error:
        print(f"FAIL 真实 WebDAV V2 兼容性探测：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
