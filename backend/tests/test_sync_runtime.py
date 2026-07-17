import unittest
from unittest.mock import patch

import sync_runtime
from storage import lock_vault
from sync_runtime import active_pending_plan, clear_pending_plan, set_pending_plan, set_runtime


class SyncRuntimeTests(unittest.TestCase):
    def test_lock_immediately_discards_pending_sync_document(self):
        set_pending_plan({
            "vault_session_id": None,
            "local_document": {"fields": [{"value": "memory-only-secret"}]},
        })
        self.assertIsNotNone(active_pending_plan())
        lock_vault()
        self.assertIsNone(active_pending_plan())

    def test_pending_join_is_not_reported_as_completed_configuration(self):
        set_pending_plan({
            "mode": "join",
            "vault_session_id": None,
            "config": {
                "base_url": "https://dav.example.invalid/root",
                "username": "tester",
                "password": "memory-only-password",
                "device_name": "测试设备",
                "vault_id": "11111111-1111-4111-8111-111111111111",
                "sync_key": "unused-in-public-status",
                "auto_sync": True,
            },
        })
        set_runtime("conflict", "加入同步空间前需要处理冲突", conflicts=2)
        with (
            patch.object(sync_runtime, "load_sync_config", return_value=None),
            patch.object(sync_runtime, "load_sync_base", return_value=None),
        ):
            result = sync_runtime.status()
        self.assertFalse(result["configured"])
        self.assertTrue(result["pending_join"])
        self.assertEqual(result["pending_conflicts"], 2)
        clear_pending_plan()
        set_runtime("idle")


if __name__ == "__main__":
    unittest.main()
