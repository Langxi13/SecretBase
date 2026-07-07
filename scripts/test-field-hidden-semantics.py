from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from models import FieldItem  # noqa: E402
from routes.entries import field_is_hidden, serialize_field  # noqa: E402


def test_copyable_field_can_stay_visible() -> None:
    field = FieldItem(name="用户名", value="demo-user", copyable=True, hidden=False)

    serialized = serialize_field(field)

    assert serialized["value"] == "demo-user"
    assert serialized["copyable"] is True
    assert serialized["hidden"] is False
    assert serialized["masked"] is False


def test_hidden_field_is_masked() -> None:
    field = FieldItem(name="密码", value="secret", copyable=True, hidden=True)

    serialized = serialize_field(field)

    assert serialized["value"] == "••••••"
    assert serialized["copyable"] is True
    assert serialized["hidden"] is True
    assert serialized["masked"] is True


def test_legacy_copyable_field_defaults_to_hidden() -> None:
    field = FieldItem(name="旧密码", value="legacy-secret", copyable=True)

    assert field.hidden is None
    assert field_is_hidden(field) is True


def main() -> None:
    tests = [
        test_copyable_field_can_stay_visible,
        test_hidden_field_is_masked,
        test_legacy_copyable_field_defaults_to_hidden,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
