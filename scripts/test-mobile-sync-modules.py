from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def line_count(relative_path: str) -> int:
    return len(read(relative_path).splitlines())


def assert_less_than(relative_path: str, maximum: int) -> None:
    current = line_count(relative_path)
    if current >= maximum:
        raise AssertionError(f"{relative_path} 当前 {current} 行，期望小于 {maximum}")


def main() -> None:
    dart_root = "mobile/secretbase_app/lib/src/features/sync"
    limits = {
        f"{dart_root}/mobile_sync_service.dart": 550,
        f"{dart_root}/mobile_sync_conflict_session.dart": 260,
        f"{dart_root}/mobile_sync_conflict_transport.dart": 120,
        f"{dart_root}/mobile_sync_graph.dart": 230,
        f"{dart_root}/mobile_sync_management_service.dart": 330,
        f"{dart_root}/mobile_sync_dialog.dart": 760,
        f"{dart_root}/mobile_sync_setup_form.dart": 360,
        f"{dart_root}/mobile_sync_configured_view.dart": 240,
        f"{dart_root}/mobile_sync_conflict_view.dart": 160,
        f"{dart_root}/mobile_sync_pairing.dart": 300,
        f"{dart_root}/mobile_sync_pairing_scanner.dart": 260,
        f"{dart_root}/mobile_sync_management_dialogs.dart": 400,
        f"{dart_root}/mobile_sync_auto.dart": 220,
        f"{dart_root}/mobile_webdav.dart": 600,
        f"{dart_root}/mobile_sync_merge.dart": 450,
        "mobile/secretbase_app/rust/src/mobile/runtime.rs": 1400,
        "mobile/secretbase_app/rust/src/mobile/sync_runtime.rs": 800,
        "mobile/secretbase_app/rust/src/mobile/sync.rs": 750,
    }
    for relative_path, maximum in limits.items():
        assert_less_than(relative_path, maximum)

    service = read(f"{dart_root}/mobile_sync_service.dart")
    for part in (
        "mobile_sync_conflict_session.dart",
        "mobile_sync_conflict_transport.dart",
        "mobile_sync_graph.dart",
        "mobile_sync_management_service.dart",
    ):
        if f"part '{part}';" not in service:
            raise AssertionError(f"Android 同步协调器未装配 {part}")

    runtime = read("mobile/secretbase_app/rust/src/mobile/runtime.rs")
    if 'include!("sync_runtime.rs");' not in runtime:
        raise AssertionError("Android Rust 同步运行时必须从通用 runtime 中拆出")

    sync_runtime = read("mobile/secretbase_app/rust/src/mobile/sync_runtime.rs")
    for boundary in (
        "LOCAL_VAULT_NOT_EMPTY",
        "verify_master_password(runtime, password)?",
        "PendingSyncKind::DeleteRemote",
        "sync::documents_equal",
    ):
        if boundary not in sync_runtime:
            raise AssertionError(f"Android Rust 同步安全边界缺失：{boundary}")

    auto_sync = read(f"{dart_root}/mobile_sync_auto.dart")
    if "Duration(seconds: 5)" not in auto_sync or "MobileSyncGate.busy" not in auto_sync:
        raise AssertionError("Android 自动同步必须保持防抖和全局互斥")

    print("PASS mobile sync modules")


if __name__ == "__main__":
    main()
