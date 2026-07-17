import copy
import unittest

import httpx

from sync_crypto import (
    KIND_HEAD,
    SyncCryptoError,
    decode_recovery_code,
    decrypt_bundle,
    encode_recovery_code,
    encrypt_bundle,
    generate_sync_key,
)
from sync_merge import apply_resolutions, merge_documents
from sync_remote import RemoteHead, SyncRepository
from sync_runtime import SyncServiceError, ensure_remote_progress, validated_document
from sync_webdav import MAX_REMOTE_BYTES, WebDavClient, WebDavError, normalize_webdav_url


VAULT_ID = "11111111-1111-4111-8111-111111111111"


def empty_document():
    return {
        "version": "1.0",
        "created_at": "2026-01-01T00:00:00Z",
        "app_name": "SecretBase",
        "vault_id": VAULT_ID,
        "entries": [],
        "deleted_entries": [],
        "tags_meta": {},
        "groups_meta": {},
    }


def entry(entry_id: str, title: str, value: str = "value"):
    return {
        "id": entry_id,
        "title": title,
        "url": "",
        "starred": False,
        "tags": [],
        "groups": [],
        "fields": [{"name": "账号", "value": value, "copyable": True, "hidden": False}],
        "remarks": "",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "deleted": False,
        "deleted_at": None,
    }


class SyncCryptoMergeTests(unittest.TestCase):
    def test_bundle_and_recovery_code_round_trip(self):
        key = generate_sync_key()
        payload = {"message": "同步测试", "secret": "never-plaintext"}
        encrypted = encrypt_bundle(payload, key, kind=KIND_HEAD, vault_id=VAULT_ID, object_id="head")

        self.assertNotIn(b"never-plaintext", encrypted)
        self.assertEqual(
            decrypt_bundle(encrypted, key, kind=KIND_HEAD, vault_id=VAULT_ID, object_id="head"),
            payload,
        )
        recovery_code = encode_recovery_code(VAULT_ID, key)
        self.assertEqual(decode_recovery_code(recovery_code), (VAULT_ID, key))
        self.assertEqual(decode_recovery_code(recovery_code.replace("-", " -\n ")), (VAULT_ID, key))

        damaged = bytearray(encrypted)
        damaged[-1] ^= 1
        with self.assertRaises(SyncCryptoError):
            decrypt_bundle(bytes(damaged), key, kind=KIND_HEAD, vault_id=VAULT_ID, object_id="head")

    def test_distinct_entries_merge_without_conflict(self):
        base = empty_document()
        local = copy.deepcopy(base)
        remote = copy.deepcopy(base)
        local["entries"] = [entry("local", "本机条目")]
        remote["entries"] = [entry("remote", "远端条目")]

        plan = merge_documents(base, local, remote)
        self.assertEqual(plan["conflicts"], [])
        self.assertEqual({item["id"] for item in plan["document"]["entries"]}, {"local", "remote"})

    def test_same_entry_requires_resolution_and_can_keep_both(self):
        base = empty_document()
        base["entries"] = [entry("same", "原条目", "base")]
        local = copy.deepcopy(base)
        remote = copy.deepcopy(base)
        local["entries"][0]["title"] = "本机版本"
        remote["entries"][0]["title"] = "远端版本"

        plan = merge_documents(base, local, remote)
        self.assertEqual(len(plan["conflicts"]), 1)
        resolved = apply_resolutions(plan, {"entry:same": "both"})
        titles = {item["title"] for item in resolved["entries"]}
        self.assertIn("远端版本", titles)
        self.assertIn("本机版本（本机冲突副本）", titles)
        self.assertEqual(len({item["id"] for item in resolved["entries"]}), 2)

    def test_delete_and_modify_never_silently_delete(self):
        base = empty_document()
        base["entries"] = [entry("same", "原条目")]
        local = copy.deepcopy(base)
        remote = copy.deepcopy(base)
        local["entries"] = []
        local["deleted_entries"] = [entry("same", "原条目") | {"deleted": True}]
        remote["entries"][0]["title"] = "远端已修改"

        plan = merge_documents(base, local, remote)
        self.assertEqual(plan["conflicts"][0]["conflict_id"], "entry:same")

        resolved = apply_resolutions(plan, {"entry:same": "both"})
        self.assertEqual(len(resolved["entries"]), 1)
        self.assertEqual(len(resolved["deleted_entries"]), 1)
        self.assertTrue(resolved["deleted_entries"][0]["deleted"])

    def test_public_conflict_never_contains_entry_fields(self):
        base = empty_document()
        base["entries"] = [entry("same", "原条目", "base-secret")]
        local = copy.deepcopy(base)
        remote = copy.deepcopy(base)
        local["entries"][0]["fields"][0]["value"] = "local-secret"
        remote["entries"][0]["fields"][0]["value"] = "remote-secret"

        public = merge_documents(base, local, remote)["conflicts"][0]["public"]
        serialized = str(public)
        self.assertNotIn("local-secret", serialized)
        self.assertNotIn("remote-secret", serialized)
        self.assertEqual(public["local"]["field_count"], 1)

    def test_malformed_remote_history_is_rejected_as_controlled_error(self):
        repository = SyncRepository(object(), vault_id=VAULT_ID, sync_key=generate_sync_key())
        payload = {
            "schema_version": 1,
            "vault_id": VAULT_ID,
            "generation": 1,
            "current_snapshot_id": "22222222-2222-4222-8222-222222222222",
            "history": ["not-an-object"],
        }
        with self.assertRaises(WebDavError) as context:
            repository._validate_head(payload)
        self.assertEqual(context.exception.code, "SYNC_HEAD_INVALID")

    def test_sync_document_rejects_duplicate_entry_ids(self):
        document = empty_document()
        document["entries"] = [entry("same", "活动条目")]
        document["deleted_entries"] = [entry("same", "回收站条目") | {"deleted": True}]
        with self.assertRaises(SyncServiceError):
            validated_document(document)

    def test_snapshot_rejects_inner_vault_identity_mismatch(self):
        repository = SyncRepository(object(), vault_id=VAULT_ID, sync_key=generate_sync_key())
        snapshot_id = "22222222-2222-4222-8222-222222222222"
        payload = {
            "schema_version": 1,
            "vault_id": VAULT_ID,
            "snapshot_id": snapshot_id,
            "parents": [],
            "created_at": "2026-01-01T00:00:00Z",
            "device_id": "33333333-3333-4333-8333-333333333333",
            "device_name": "测试设备",
            "document": empty_document() | {"vault_id": "44444444-4444-4444-8444-444444444444"},
        }
        with self.assertRaises(WebDavError):
            repository._validate_snapshot(payload, snapshot_id)

    def test_production_webdav_rejects_loopback_http(self):
        with self.assertRaises(WebDavError) as context:
            normalize_webdav_url("http://127.0.0.1:8080/dav")
        self.assertEqual(context.exception.code, "INSECURE_WEBDAV_URL")

    def test_webdav_stream_rejects_oversized_declared_content(self):
        def handler(_request):
            return httpx.Response(
                200,
                headers={
                    "ETag": '"fixture"',
                    "Content-Length": str(MAX_REMOTE_BYTES + 1),
                },
                content=b"",
            )

        client = WebDavClient("https://dav.example.invalid/root", "tester", "password")
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with self.assertRaises(WebDavError) as context:
                client.get("oversized.bin")
            self.assertEqual(context.exception.code, "WEBDAV_OBJECT_TOO_LARGE")
        finally:
            client.close()

    def test_webdav_rejects_unquoted_etag(self):
        def handler(_request):
            return httpx.Response(200, headers={"ETag": "not-quoted"}, content=b"fixture")

        client = WebDavClient("https://dav.example.invalid/root", "tester", "password")
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with self.assertRaises(WebDavError) as context:
                client.get("invalid-etag.bin")
            self.assertEqual(context.exception.code, "WEBDAV_ETAG_UNSUPPORTED")
        finally:
            client.close()

    def test_publish_rejects_document_from_another_vault(self):
        repository = SyncRepository(object(), vault_id=VAULT_ID, sync_key=generate_sync_key())
        with self.assertRaises(WebDavError) as context:
            repository.publish(
                empty_document() | {"vault_id": "55555555-5555-4555-8555-555555555555"},
                current_head=None,
                device_id="33333333-3333-4333-8333-333333333333",
                device_name="测试设备",
            )
        self.assertEqual(context.exception.code, "SYNC_DOCUMENT_INVALID")

    def test_key_rotation_can_defer_old_snapshot_cleanup_until_local_commit(self):
        class FakeClient:
            def __init__(self):
                self.deleted = []

            @staticmethod
            def snapshot_path(vault_id, snapshot_id):
                return "root", vault_id, "snapshots", snapshot_id

            @staticmethod
            def head_path(vault_id):
                return "root", vault_id, "head"

            @staticmethod
            def put(_content, *_segments, **_conditions):
                return '"new-etag"'

            def delete(self, *segments, **_options):
                self.deleted.append(segments)

        client = FakeClient()
        repository = SyncRepository(client, vault_id=VAULT_ID, sync_key=generate_sync_key())
        old_snapshot = "22222222-2222-4222-8222-222222222222"
        current_head = RemoteHead(
            payload={
                "generation": 3,
                "current_snapshot_id": old_snapshot,
                "history": [{"snapshot_id": old_snapshot}],
            },
            etag='"old-etag"',
        )
        _head, _snapshot, dropped = repository.publish(
            empty_document(),
            current_head=current_head,
            device_id="33333333-3333-4333-8333-333333333333",
            device_name="测试设备",
            reset_history=True,
            cleanup_history=False,
        )
        self.assertEqual(dropped, [old_snapshot])
        self.assertEqual(client.deleted, [])

    def test_same_generation_different_snapshot_is_rejected_as_remote_fork(self):
        base_snapshot = "22222222-2222-4222-8222-222222222222"
        remote_snapshot = "55555555-5555-4555-8555-555555555555"
        head = RemoteHead(
            payload={
                "generation": 4,
                "current_snapshot_id": remote_snapshot,
                "history": [{"snapshot_id": remote_snapshot}],
            },
            etag='"remote"',
        )
        with self.assertRaises(SyncServiceError) as context:
            ensure_remote_progress(head, {"generation": 4, "snapshot_id": base_snapshot})
        self.assertEqual(context.exception.code, "SYNC_REMOTE_ROLLBACK")

    def test_key_rotation_floor_allows_recovery_from_local_base_save_failure(self):
        base_snapshot = "22222222-2222-4222-8222-222222222222"
        rotated_snapshot = "55555555-5555-4555-8555-555555555555"
        head = RemoteHead(
            payload={
                "generation": 5,
                "current_snapshot_id": rotated_snapshot,
                "history": [{"snapshot_id": rotated_snapshot}],
            },
            etag='"rotated"',
        )
        ensure_remote_progress(
            head,
            {"generation": 4, "snapshot_id": base_snapshot},
            {
                "history_floor_generation": 5,
                "history_floor_snapshot_id": rotated_snapshot,
            },
        )


if __name__ == "__main__":
    unittest.main()
