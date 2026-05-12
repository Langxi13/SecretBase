from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
BACKEND_ENV = BACKEND_DIR / ".env"


def run_config_probe(code: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    probe_env = {
        key: value
        for key, value in os.environ.items()
        if not (
            key.startswith("SECRETBASE_")
            or key in {
                "HOST",
                "PORT",
                "DATA_DIR",
                "BACKUP_DIR",
                "LOG_DIR",
                "VAULT_PATH",
                "SETTINGS_PATH",
                "CORS_ORIGINS",
                "AI_MODEL",
                "AI_API_KEY",
                "AI_API_URL",
                "DEEPSEEK_API_KEY",
                "LOG_LEVEL",
            }
        )
    }
    probe_env.update(env)
    probe_env["PYTHONPATH"] = str(BACKEND_DIR)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=probe_env,
        text=True,
        capture_output=True,
        check=False,
    )


def with_backend_env(content: str, fn) -> None:
    original = BACKEND_ENV.read_text(encoding="utf-8") if BACKEND_ENV.exists() else None
    BACKEND_ENV.write_text(content, encoding="utf-8")
    try:
        fn()
    finally:
        if original is None:
            try:
                BACKEND_ENV.unlink()
            except FileNotFoundError:
                pass
        else:
            BACKEND_ENV.write_text(original, encoding="utf-8")


def assert_probe_ok(result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode != 0:
        raise AssertionError(
            f"probe failed with code {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def test_server_mode_loads_dotenv_without_overriding_system_env() -> None:
    def probe() -> None:
        result = run_config_probe(
            """
import config
assert hasattr(config, "RuntimeConfig")
assert config.APP_MODE == "server"
assert config.PORT == 54321
assert config.AI_MODEL == "dotenv-model"
assert config.RUNTIME_CONFIG.port == 54321
assert config.RUNTIME_CONFIG.ai_model == "dotenv-model"
""",
            {"PORT": "54321"},
        )
        assert_probe_ok(result)

    with_backend_env("PORT=12345\nAI_MODEL=dotenv-model\n", probe)


def test_desktop_mode_does_not_load_backend_dotenv() -> None:
    def probe() -> None:
        result = run_config_probe(
            """
import config
assert config.APP_MODE == "desktop"
assert config.AI_MODEL == "deepseek-v4-flash"
assert config.RUNTIME_CONFIG.mode == "desktop"
""",
            {"SECRETBASE_MODE": "desktop"},
        )
        assert_probe_ok(result)

    with_backend_env("AI_MODEL=dotenv-should-not-load\n", probe)


def test_importing_config_does_not_create_runtime_directories() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        data_dir = root / "data"
        backup_dir = root / "data" / "backups"
        log_dir = root / "logs"
        settings_path = root / "config" / "settings.json"
        result = run_config_probe(
            """
from pathlib import Path
import os
import config
assert hasattr(config, "ensure_runtime_dirs")
for key in ["DATA_DIR", "BACKUP_DIR", "LOG_DIR"]:
    assert not Path(os.environ[key]).exists(), key
assert not Path(os.environ["SETTINGS_PATH"]).parent.exists()
""",
            {
                "DATA_DIR": str(data_dir),
                "BACKUP_DIR": str(backup_dir),
                "LOG_DIR": str(log_dir),
                "SETTINGS_PATH": str(settings_path),
            },
        )
        assert_probe_ok(result)


def test_ensure_runtime_dirs_creates_required_directories() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        data_dir = root / "data"
        backup_dir = root / "data" / "backups"
        log_dir = root / "logs"
        settings_path = root / "settings.json"
        result = run_config_probe(
            """
from pathlib import Path
import config
config.ensure_runtime_dirs()
assert Path(config.DATA_DIR).is_dir()
assert Path(config.BACKUP_DIR).is_dir()
assert Path(config.LOG_DIR_PATH).is_dir()
assert Path(config.VAULT_PATH).parent.is_dir()
assert Path(config.SETTINGS_PATH).parent.is_dir()
""",
            {
                "DATA_DIR": str(data_dir),
                "BACKUP_DIR": str(backup_dir),
                "LOG_DIR": str(log_dir),
                "SETTINGS_PATH": str(settings_path),
            },
        )
        assert_probe_ok(result)


def test_importing_main_initializes_runtime_directories() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        data_dir = root / "data"
        backup_dir = root / "data" / "backups"
        log_dir = root / "logs"
        settings_path = root / "config" / "settings.json"
        result = run_config_probe(
            """
from pathlib import Path
import config
import main
assert Path(config.DATA_DIR).is_dir()
assert Path(config.BACKUP_DIR).is_dir()
assert Path(config.LOG_DIR_PATH).is_dir()
assert Path(config.VAULT_PATH).parent.is_dir()
assert Path(config.SETTINGS_PATH).parent.is_dir()
""",
            {
                "DATA_DIR": str(data_dir),
                "BACKUP_DIR": str(backup_dir),
                "LOG_DIR": str(log_dir),
                "SETTINGS_PATH": str(settings_path),
            },
        )
        assert_probe_ok(result)


def test_runtime_config_endpoint_returns_javascript() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        result = run_config_probe(
            """
from fastapi.testclient import TestClient
import main
client = TestClient(main.app)
response = client.get("/secretbase-runtime-config.js")
assert response.status_code == 200
assert "javascript" in response.headers["content-type"]
assert "window.SECRETBASE_RUNTIME_CONFIG" in response.text
assert '"apiBaseUrl": ""' in response.text
assert '"mode": "desktop"' in response.text
""",
            {
                "SECRETBASE_MODE": "desktop",
                "DATA_DIR": str(root / "data"),
                "BACKUP_DIR": str(root / "data" / "backups"),
                "LOG_DIR": str(root / "logs"),
                "SETTINGS_PATH": str(root / "settings.json"),
            },
        )
        assert_probe_ok(result)


def test_desktop_mode_serves_frontend_index() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        result = run_config_probe(
            """
from fastapi.testclient import TestClient
import main
client = TestClient(main.app)
index_response = client.get("/")
assert index_response.status_code == 200
assert "text/html" in index_response.headers["content-type"]
assert '<div id="app">' in index_response.text
asset_response = client.get("/css/style.css")
assert asset_response.status_code == 200
assert "text/css" in asset_response.headers["content-type"]
""",
            {
                "SECRETBASE_MODE": "desktop",
                "DATA_DIR": str(root / "data"),
                "BACKUP_DIR": str(root / "data" / "backups"),
                "LOG_DIR": str(root / "logs"),
                "SETTINGS_PATH": str(root / "settings.json"),
            },
        )
        assert_probe_ok(result)


def main() -> None:
    tests = [
        test_server_mode_loads_dotenv_without_overriding_system_env,
        test_desktop_mode_does_not_load_backend_dotenv,
        test_importing_config_does_not_create_runtime_directories,
        test_ensure_runtime_dirs_creates_required_directories,
        test_importing_main_initializes_runtime_directories,
        test_runtime_config_endpoint_returns_javascript,
        test_desktop_mode_serves_frontend_index,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
