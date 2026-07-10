from __future__ import annotations

import os
import json
import re
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from desktop import launcher  # noqa: E402


BACKEND_DIR = PROJECT_ROOT / "backend"
BACKEND_ENV = BACKEND_DIR / ".env"
LAUNCHER = PROJECT_ROOT / "desktop" / "launcher.py"
DEV_TEST_BACKEND = PROJECT_ROOT / "scripts" / "dev-test-backend.sh"


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
assert config.RUNTIME_CONFIG.port == 54321
assert not any(name.startswith("ai_") for name in config.RUNTIME_CONFIG.__dataclass_fields__)
""",
            {"PORT": "54321"},
        )
        assert_probe_ok(result)

    with_backend_env("PORT=12345\n", probe)


def test_server_settings_default_inside_data_dir() -> None:
    with tempfile.TemporaryDirectory() as raw:
        data_dir = Path(raw) / "data"

        def probe() -> None:
            result = run_config_probe(
                """
from pathlib import Path
import config
assert Path(config.SETTINGS_PATH) == Path(config.DATA_DIR) / "settings.json"
assert not Path(config.DATA_DIR).exists()
""",
                {"DATA_DIR": str(data_dir)},
            )
            assert_probe_ok(result)

        with_backend_env("", probe)


def test_desktop_mode_does_not_load_backend_dotenv() -> None:
    def probe() -> None:
        result = run_config_probe(
            """
import config
assert config.APP_MODE == "desktop"
assert config.RUNTIME_CONFIG.mode == "desktop"
assert config.CORS_ORIGINS == "http://127.0.0.1:10004"
assert not any(name.startswith("ai_") for name in config.RUNTIME_CONFIG.__dataclass_fields__)
""",
            {"SECRETBASE_MODE": "desktop"},
        )
        assert_probe_ok(result)

    with_backend_env("PORT=12345\n", probe)


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
assert Path(config.SECURE_SETTINGS_FILE).parent == Path(config.DATA_DIR)
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
client = TestClient(main.app, base_url="http://127.0.0.1")
response = client.get("/secretbase-runtime-config.js")
assert response.status_code == 200
assert "javascript" in response.headers["content-type"]
assert "window.SECRETBASE_RUNTIME_CONFIG" in response.text
assert '"apiBaseUrl": ""' in response.text
assert '"mode": "desktop"' in response.text
assert '"version": "3.1.0"' in response.text
assert response.headers["x-frame-options"] == "DENY"
assert response.headers["referrer-policy"] == "no-referrer"
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
client = TestClient(main.app, base_url="http://127.0.0.1")
index_response = client.get("/")
assert index_response.status_code == 200
assert "text/html" in index_response.headers["content-type"]
assert '<div id="app"' in index_response.text
assert 'js/template-loader.js' in index_response.text
assert 'js/app.js' in index_response.text
assert 'vendor/vue/vue.global.prod.js' in index_response.text
assert 'https://unpkg.com' not in index_response.text
assert 'fonts.googleapis.com' not in index_response.text

settings_response = client.get("/templates/settings-dialog.html")
assert settings_response.status_code == 200
assert "text/html" in settings_response.headers["content-type"]
assert 'class="settings-tabs"' in settings_response.text
assert "AI 配置" in settings_response.text
assert "当前 AI 配置" in settings_response.text
assert "修改配置" in settings_response.text
assert "取消修改" in settings_response.text
assert "ai-config-summary" in settings_response.text
assert "当前已保存" in settings_response.text
assert "aiConfiguredBaseUrl" in settings_response.text

ai_response = client.get("/templates/ai-dialog.html")
assert ai_response.status_code == 200
assert "清空解析" in ai_response.text
assert "去配置 AI" in ai_response.text
assert "@click.self" not in settings_response.text
for asset_path in (
    "/css/base.css",
    "/css/workspace.css",
    "/css/modals.css",
    "/css/management-components.css",
    "/js/app-state.js",
    "/js/app-feature-composition.js",
    "/js/store-state.js",
    "/js/store-taxonomy-methods.js",
):
    asset_response = client.get(asset_path)
    assert asset_response.status_code == 200, asset_path
    expected_content_type = "text/css" if asset_path.endswith(".css") else "javascript"
    assert expected_content_type in asset_response.headers["content-type"], asset_path
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


def test_api_prefix_aliases_work_in_desktop_mode() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        result = run_config_probe(
            """
from fastapi.testclient import TestClient
import main
client = TestClient(main.app, base_url="http://127.0.0.1")
status_response = client.get("/api/auth/status")
assert status_response.status_code == 200
init_response = client.post("/api/auth/init", json={"password": "desktop-alias-pass"})
assert init_response.status_code == 200
token = init_response.json()["data"]["token"]
ai_response = client.get("/api/ai/status", headers={"X-SecretBase-Token": token})
assert ai_response.status_code == 200
assert ai_response.json()["data"]["configured"] is False
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


def test_launcher_dry_run_reports_desktop_paths() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        result = subprocess.run(
            [sys.executable, str(LAUNCHER), "--dry-run"],
            cwd=PROJECT_ROOT,
            env={**os.environ, "SECRETBASE_DESKTOP_DATA_ROOT": str(root)},
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(f"dry-run failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        data = json.loads(result.stdout)
        assert data["mode"] == "desktop"
        assert data["host"] == "127.0.0.1"
        assert int(data["port"]) > 0
        assert data["data_root"] == str(root.resolve())
        assert data["vault_path"] == str((root / "data" / "secretbase.enc").resolve())
        assert data["backup_dir"] == str((root / "data" / "backups").resolve())
        assert data["log_dir"] == str((root / "logs").resolve())
        assert data["settings_path"] == str((root / "settings.json").resolve())
        assert not (root / "data").exists()


def test_launcher_data_root_argument_overrides_environment() -> None:
    with tempfile.TemporaryDirectory() as raw:
        requested_root = Path(raw) / "requested"
        ignored_root = Path(raw) / "ignored"
        result = subprocess.run(
            [sys.executable, str(LAUNCHER), "--dry-run", "--data-root", str(requested_root)],
            cwd=PROJECT_ROOT,
            env={**os.environ, "SECRETBASE_DESKTOP_DATA_ROOT": str(ignored_root)},
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(f"dry-run failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        data = json.loads(result.stdout)
        assert data["data_root"] == str(requested_root.resolve())
        assert not requested_root.exists()


def test_desktop_launcher_forces_loopback_security() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        original_cors = os.environ.get("CORS_ORIGINS")
        os.environ["CORS_ORIGINS"] = "*"
        try:
            env = launcher.build_desktop_env(root, 45678)
        finally:
            if original_cors is None:
                os.environ.pop("CORS_ORIGINS", None)
            else:
                os.environ["CORS_ORIGINS"] = original_cors
        assert env["HOST"] == "127.0.0.1"
        assert env["CORS_ORIGINS"] == "http://127.0.0.1:45678"
        assert env["PYTHONUNBUFFERED"] == "1"
        assert env["PYTHONUTF8"] == "1"
        assert env["PYTHONIOENCODING"] == "utf-8"
        assert env["SECRETBASE_FRONTEND_DIR"] == str((PROJECT_ROOT / "frontend").resolve())


def test_in_process_desktop_server_starts_and_stops() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        result = run_config_probe(
            """
import json
import os
import urllib.request
from pathlib import Path
from desktop.runtime import InProcessDesktopServer

root = Path(os.environ["SECRETBASE_TEST_DATA_ROOT"])
server = InProcessDesktopServer(root)
try:
    url = server.start()
    assert server.is_running
    with urllib.request.urlopen(f"{url}/health", timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    assert response.status == 200
    assert payload["data"]["status"] == "healthy"
    with urllib.request.urlopen(f"{url}/", timeout=5) as response:
        html = response.read().decode("utf-8")
    assert '<div id="app"' in html
finally:
    server.stop()
assert not server.is_running
assert (root / "data").is_dir()
assert (root / "webview").is_dir()
""",
            {"SECRETBASE_TEST_DATA_ROOT": str(root)},
        )
        assert_probe_ok(result)


def test_desktop_rejects_untrusted_host() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        result = run_config_probe(
            """
from fastapi.testclient import TestClient
import main
client = TestClient(main.app, base_url="http://malicious.example")
response = client.get("/health")
assert response.status_code == 400
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


def test_launcher_no_browser_starts_health_endpoint() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        process = subprocess.Popen(
            [sys.executable, str(LAUNCHER), "--no-browser"],
            cwd=PROJECT_ROOT,
            env={**os.environ, "SECRETBASE_DESKTOP_DATA_ROOT": str(root)},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0,
        )
        output: list[str] = []
        try:
            deadline = time.time() + 20
            url = None
            while time.time() < deadline:
                line = process.stdout.readline() if process.stdout else ""
                if line:
                    output.append(line)
                    match = re.search(r"http://127\.0\.0\.1:\d+", line)
                    if match:
                        url = match.group(0)
                        break
                if process.poll() is not None:
                    break
            if not url:
                raise AssertionError(f"launcher did not print URL. Output:\n{''.join(output)}")

            with urllib.request.urlopen(f"{url}/health", timeout=5) as response:
                body = response.read().decode("utf-8")
            assert response.status == 200
            assert '"healthy"' in body
            assert (root / "data").is_dir()
            assert (root / "logs").is_dir()
            if os.name != "nt":
                assert root.stat().st_mode & 0o077 == 0
        finally:
            if process.poll() is None:
                if os.name == "nt":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_dev_test_backend_script_uses_isolated_runtime() -> None:
    assert DEV_TEST_BACKEND.exists()
    content = DEV_TEST_BACKEND.read_text(encoding="utf-8")
    assert "SECRETBASE_TEST_DATA_ROOT" in content
    assert "/tmp/secretbase-test-runtime" in content
    assert "SECRETBASE_TEST_PASSWORD" in content
    assert "SecretBase-Test-123456!" in content
    assert "SECRETBASE_TEST_PORT" in content
    assert "10014" in content
    assert "--reset" in content
    assert "rm -rf" in content
    assert "DATA_DIR=" in content
    assert "VAULT_PATH=" in content
    assert "SETTINGS_PATH=" in content
    assert "BACKUP_DIR=" in content
    assert "LOG_DIR=" in content
    assert "backend/data" not in content
    assert "backend/settings.json" not in content
    assert "unset DEEPSEEK_API_KEY" in content
    assert "unset AI_API_KEY" in content
    assert "unset AI_MODEL" in content
    assert "unset AI_API_URL" in content


def main() -> None:
    tests = [
        test_server_mode_loads_dotenv_without_overriding_system_env,
        test_server_settings_default_inside_data_dir,
        test_desktop_mode_does_not_load_backend_dotenv,
        test_importing_config_does_not_create_runtime_directories,
        test_ensure_runtime_dirs_creates_required_directories,
        test_importing_main_initializes_runtime_directories,
        test_runtime_config_endpoint_returns_javascript,
        test_desktop_mode_serves_frontend_index,
        test_api_prefix_aliases_work_in_desktop_mode,
        test_launcher_dry_run_reports_desktop_paths,
        test_launcher_data_root_argument_overrides_environment,
        test_desktop_launcher_forces_loopback_security,
        test_in_process_desktop_server_starts_and_stops,
        test_desktop_rejects_untrusted_host,
        test_launcher_no_browser_starts_health_endpoint,
        test_dev_test_backend_script_uses_isolated_runtime,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
