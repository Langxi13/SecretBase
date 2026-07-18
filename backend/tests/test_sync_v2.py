import copy
import unittest
import uuid
from contextlib import nullcontext
from types import SimpleNamespace
from unittest import mock

from sync_v2_crypto import (
    decode_recovery_code,
    decrypt_snapshot,
    encode_recovery_code,
    encrypt_snapshot,
    pairing_uri,
)
from sync_v2_remote import SyncV2Repository
import sync_v2_management
from sync_v2_service import _documents_equal, _fold_remote_documents, _remote_document
from sync_merge import apply_resolutions
from sync_webdav import RemoteChild, RemoteObject, SYNC_ROOT_V2


VAULT_ID = "11111111-1111-4111-8111-111111111111"
SPACE_ID = "22222222-2222-4222-8222-222222222222"
KEY = b"k" * 32
DEVICE_A = "33333333-3333-4333-8333-333333333333"
DEVICE_B = "44444444-4444-4444-8444-444444444444"


def document(title: str) -> dict:
    return {
        "version": "1.0",
        "created_at": "2026-01-01T00:00:00Z",
        "app_name": "SecretBase",
        "vault_id": VAULT_ID,
        "entries": [{"id": title, "title": title, "fields": []}],
        "deleted_entries": [],
        "tags_meta": {},
        "groups_meta": {},
    }


def same_entry_document(title: str) -> dict:
    value = document("same")
    value["entries"][0]["title"] = title
    return value


class MemoryDav:
    """A deliberately weak WebDAV store: no ETag and no conditional semantics."""

    def __init__(self):
        self.collections = {("dav",)}
        self.objects = {}

    def ensure_v2_layout(self, vault_id, space_id, device_id=None):
        paths = [
            (SYNC_ROOT_V2,),
            (SYNC_ROOT_V2, vault_id),
            (SYNC_ROOT_V2, vault_id, space_id),
            (SYNC_ROOT_V2, vault_id, space_id, "snapshots"),
        ]
        if device_id:
            paths.append((*paths[-1], device_id))
        self.collections.update(paths)

    @staticmethod
    def v2_snapshots_path(vault_id, space_id):
        return SYNC_ROOT_V2, vault_id, space_id, "snapshots"

    @staticmethod
    def v2_device_path(vault_id, space_id, device_id):
        return SYNC_ROOT_V2, vault_id, space_id, "snapshots", device_id

    def v2_snapshot_path(self, vault_id, space_id, device_id, generation, snapshot_id):
        return (*self.v2_device_path(vault_id, space_id, device_id), f"{generation}-{snapshot_id}.sbs")

    def put_unconditional(self, content, *path):
        self.objects[path] = bytes(content)

    def get(self, *path, optional=False, require_etag=False):
        if path not in self.objects:
            if optional:
                return None
            raise RuntimeError("missing")
        return RemoteObject(self.objects[path], "")

    def list_children(self, *path, optional=False):
        if path not in self.collections:
            if optional:
                return []
            raise RuntimeError("missing collection")
        names = {}
        for collection in self.collections:
            if len(collection) == len(path) + 1 and collection[:len(path)] == path:
                names[collection[-1]] = RemoteChild(collection[-1], True)
        for object_path, content in self.objects.items():
            if len(object_path) == len(path) + 1 and object_path[:len(path)] == path:
                names[object_path[-1]] = RemoteChild(object_path[-1], False, len(content))
        return sorted(names.values(), key=lambda item: item.name)

    def delete(self, *path, optional=True, if_match=None):
        self.objects.pop(path, None)
        self.collections.discard(path)


class SyncV2Tests(unittest.TestCase):
    def test_document_equality_ignores_entry_collection_order(self):
        left = document("first")
        left["entries"].append({"id": "second", "title": "second", "fields": []})
        right = copy.deepcopy(left)
        right["entries"].reverse()
        self.assertTrue(_documents_equal(left, right))

    def test_single_frontier_returns_snapshot_without_reordering(self):
        dav = MemoryDav()
        repo = SyncV2Repository(dav, vault_id=VAULT_ID, space_id=SPACE_ID, sync_key=KEY)
        repo.ensure_layout(DEVICE_A)
        value = document("first")
        value["entries"].append({"id": "second", "title": "second", "fields": []})
        snapshot = repo.publish(
            value,
            parents=[],
            generation=1,
            device_id=DEVICE_A,
            device_name="设备 A",
        )
        graph = repo.discover()
        remote, plan, continuation = _remote_document(graph)
        self.assertEqual([item["id"] for item in remote["entries"]], ["first", "second"])
        self.assertIsNone(plan)
        self.assertIsNone(continuation)
        self.assertEqual(graph.frontier, (snapshot.snapshot_id,))

    def test_bundle_and_recovery_are_round_trip_and_private(self):
        snapshot_id = str(uuid.uuid4())
        payload = {
            "schema_version": 2,
            "protocol": "snapshot-dag",
            "vault_id": VAULT_ID,
            "space_id": SPACE_ID,
            "snapshot_id": snapshot_id,
            "generation": 1,
            "parents": [],
            "document": {"secret": "never-on-webdav"},
        }
        encrypted = encrypt_snapshot(payload, KEY, vault_id=VAULT_ID, space_id=SPACE_ID, snapshot_id=snapshot_id)
        self.assertNotIn(b"never-on-webdav", encrypted)
        self.assertEqual(
            decrypt_snapshot(encrypted, KEY, vault_id=VAULT_ID, space_id=SPACE_ID, snapshot_id=snapshot_id),
            payload,
        )
        recovery = encode_recovery_code(VAULT_ID, SPACE_ID, KEY)
        self.assertEqual(decode_recovery_code(recovery), (VAULT_ID, SPACE_ID, KEY))

        pairing = pairing_uri(
            vault_id=VAULT_ID,
            space_id=SPACE_ID,
            key=KEY,
            base_url="https://dav.example.test/secretbase",
            username="tester",
            recovery_code=recovery,
        )
        self.assertIn("recovery_code=", pairing)
        self.assertNotIn("key=", pairing)
        self.assertNotIn("password=", pairing)
        with self.assertRaises(ValueError):
            pairing_uri(
                vault_id=VAULT_ID,
                space_id=SPACE_ID,
                key=b"x" * 32,
                base_url="https://dav.example.test/secretbase",
                username="tester",
                recovery_code=recovery,
            )

    def test_repository_discovers_concurrent_frontier_without_etag(self):
        dav = MemoryDav()
        first = SyncV2Repository(dav, vault_id=VAULT_ID, space_id=SPACE_ID, sync_key=KEY)
        first.ensure_layout(DEVICE_A)
        root = first.publish(
            document("root"),
            parents=[],
            generation=1,
            device_id=DEVICE_A,
            device_name="设备 A",
        )
        branch_a = first.publish(
            document("a"),
            parents=[root.snapshot_id],
            generation=2,
            device_id=DEVICE_A,
            device_name="设备 A",
        )
        second = SyncV2Repository(dav, vault_id=VAULT_ID, space_id=SPACE_ID, sync_key=KEY)
        second.ensure_layout(DEVICE_B)
        branch_b = second.publish(
            document("b"),
            parents=[root.snapshot_id],
            generation=2,
            device_id=DEVICE_B,
            device_name="设备 B",
        )
        graph = first.discover()
        self.assertEqual(set(graph.frontier), {branch_a.snapshot_id, branch_b.snapshot_id})
        self.assertEqual(graph.get(root.snapshot_id).generation, 1)
        self.assertEqual(len(graph.list_history() if hasattr(graph, "list_history") else graph.snapshots), 3)

    def test_corrupt_or_missing_parent_stops_discovery(self):
        dav = MemoryDav()
        repo = SyncV2Repository(dav, vault_id=VAULT_ID, space_id=SPACE_ID, sync_key=KEY)
        repo.ensure_layout(DEVICE_A)
        snapshot_id = str(uuid.uuid4())
        payload = {
            "schema_version": 2,
            "protocol": "snapshot-dag",
            "vault_id": VAULT_ID,
            "space_id": SPACE_ID,
            "snapshot_id": snapshot_id,
            "generation": 2,
            "parents": [str(uuid.uuid4())],
            "created_at": "2026-01-01T00:00:00Z",
            "device_id": DEVICE_A,
            "device_name": "设备 A",
            "document": document("bad"),
        }
        content = encrypt_snapshot(payload, KEY, vault_id=VAULT_ID, space_id=SPACE_ID, snapshot_id=snapshot_id)
        path = repo.client.v2_snapshot_path(VAULT_ID, SPACE_ID, DEVICE_A, 2, snapshot_id)
        dav.put_unconditional(content, *path)
        with self.assertRaises(Exception) as context:
            repo.discover()
        self.assertIn("parent", str(context.exception))

    def test_generation_gaps_stop_discovery(self):
        dav = MemoryDav()
        repo = SyncV2Repository(dav, vault_id=VAULT_ID, space_id=SPACE_ID, sync_key=KEY)
        repo.ensure_layout(DEVICE_A)
        root = repo.publish(
            document("root"),
            parents=[],
            generation=1,
            device_id=DEVICE_A,
            device_name="设备 A",
        )
        snapshot_id = str(uuid.uuid4())
        payload = {
            "schema_version": 2,
            "protocol": "snapshot-dag",
            "vault_id": VAULT_ID,
            "space_id": SPACE_ID,
            "snapshot_id": snapshot_id,
            "generation": 4,
            "parents": [root.snapshot_id],
            "created_at": "2026-01-01T00:00:00Z",
            "device_id": DEVICE_A,
            "device_name": "设备 A",
            "document": document("gap"),
        }
        content = encrypt_snapshot(
            payload,
            KEY,
            vault_id=VAULT_ID,
            space_id=SPACE_ID,
            snapshot_id=snapshot_id,
        )
        path = repo.client.v2_snapshot_path(VAULT_ID, SPACE_ID, DEVICE_A, 4, snapshot_id)
        dav.put_unconditional(content, *path)
        with self.assertRaises(Exception) as context:
            repo.discover()
        self.assertIn("generation", str(context.exception))

    def test_root_publish_requires_generation_one(self):
        dav = MemoryDav()
        repo = SyncV2Repository(dav, vault_id=VAULT_ID, space_id=SPACE_ID, sync_key=KEY)
        with self.assertRaises(Exception) as context:
            repo.publish(
                document("invalid-root"),
                parents=[],
                generation=2,
                device_id=DEVICE_A,
                device_name="设备 A",
            )
        self.assertIn("generation", str(context.exception))

    def test_repository_rejects_excessive_aggregate_history_size(self):
        dav = MemoryDav()
        repo = SyncV2Repository(dav, vault_id=VAULT_ID, space_id=SPACE_ID, sync_key=KEY)
        repo.ensure_layout(DEVICE_A)
        repo.publish(
            document("root"),
            parents=[],
            generation=1,
            device_id=DEVICE_A,
            device_name="设备 A",
        )
        with mock.patch("sync_v2_remote.MAX_REMOTE_HISTORY_BYTES", 1):
            with self.assertRaises(Exception) as context:
                repo.discover()
        self.assertIn("历史", str(context.exception))

    def test_remote_cleanup_preserves_unknown_objects(self):
        dav = MemoryDav()
        repo = SyncV2Repository(dav, vault_id=VAULT_ID, space_id=SPACE_ID, sync_key=KEY)
        repo.ensure_layout(DEVICE_A)
        repo.publish(
            document("root"),
            parents=[],
            generation=1,
            device_id=DEVICE_A,
            device_name="设备 A",
        )
        unknown = (*dav.v2_device_path(VAULT_ID, SPACE_ID, DEVICE_A), "notes.txt")
        dav.put_unconditional(b"keep-me", *unknown)

        with self.assertRaises(Exception):
            repo.delete_remote()

        self.assertEqual(dav.objects[unknown], b"keep-me")

    def test_key_rotation_restores_previous_local_state_when_new_base_save_fails(self):
        old_config = {
            "protocol_version": 2,
            "space_id": SPACE_ID,
            "sync_key": "old-key",
            "device_id": DEVICE_A,
            "device_name": "设备 A",
        }
        old_base = {"protocol_version": 2, "space_id": SPACE_ID, "document": document("root")}
        old_remote = mock.Mock()
        new_remote = mock.Mock()
        old_graph = object()
        old_remote.discover.return_value = old_graph
        new_remote.publish.return_value = SimpleNamespace(snapshot_id=str(uuid.uuid4()))

        with (
            mock.patch.object(sync_v2_management, "verify_master_password"),
            mock.patch.object(sync_v2_management, "load_sync_config", return_value=old_config),
            mock.patch.object(sync_v2_management, "load_sync_base", return_value=old_base),
            mock.patch.object(sync_v2_management, "client", return_value=nullcontext(object())),
            mock.patch.object(
                sync_v2_management,
                "_repository",
                side_effect=[old_remote, new_remote],
            ),
            mock.patch.object(
                sync_v2_management,
                "_remote_document",
                return_value=(document("root"), None, None),
            ),
            mock.patch.object(sync_v2_management, "_new_key", return_value=b"n" * 32),
            mock.patch.object(sync_v2_management, "save_sync_config") as save_config,
            mock.patch.object(
                sync_v2_management,
                "_save_base",
                side_effect=OSError("simulated base write failure"),
            ),
            mock.patch.object(sync_v2_management, "save_sync_base") as save_base,
        ):
            with self.assertRaises(OSError):
                sync_v2_management.rotate_key("master")

        self.assertEqual(save_config.call_args_list[-1], mock.call(old_config))
        save_base.assert_called_once_with(old_base)

    def test_three_remote_frontiers_keep_unprocessed_branches_until_resolution(self):
        dav = MemoryDav()
        repo = SyncV2Repository(dav, vault_id=VAULT_ID, space_id=SPACE_ID, sync_key=KEY)
        repo.ensure_layout(DEVICE_A)
        root = repo.publish(
            same_entry_document("原始"),
            parents=[],
            generation=1,
            device_id=DEVICE_A,
            device_name="设备 A",
        )
        branches = []
        for device, title in (
            (DEVICE_A, "本机分支"),
            (DEVICE_B, "远端分支 1"),
            (str(uuid.uuid4()), "远端分支 2"),
        ):
            repo.ensure_layout(device)
            branches.append(
                repo.publish(
                    same_entry_document(title),
                    parents=[root.snapshot_id],
                    generation=2,
                    device_id=device,
                    device_name=device,
                )
            )

        graph = repo.discover()
        self.assertEqual(len(graph.frontier), 3)
        remote_value, plan, continuation = _remote_document(graph)
        self.assertIsNotNone(plan)
        self.assertIsNotNone(continuation)
        self.assertEqual(len(continuation["remaining_frontier"]), 1)

        resolved = apply_resolutions(plan, {plan["conflicts"][0]["conflict_id"]: "remote"})
        final, next_plan, next_continuation = _fold_remote_documents(
            graph,
            ancestor=continuation["ancestor"],
            merged=resolved,
            frontier=continuation["remaining_frontier"],
        )
        self.assertIsNotNone(next_plan)
        self.assertIsNotNone(next_continuation)
        resolved_again = apply_resolutions(
            next_plan,
            {next_plan["conflicts"][0]["conflict_id"]: "remote"},
        )
        final, last_plan, _ = _fold_remote_documents(
            graph,
            ancestor=continuation["ancestor"],
            merged=resolved_again,
            frontier=next_continuation["remaining_frontier"],
        )
        self.assertIsNone(last_plan)
        self.assertEqual(len(final["entries"]), 1)


if __name__ == "__main__":
    unittest.main()
