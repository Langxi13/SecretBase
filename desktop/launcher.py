from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from collections import deque
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"


def choose_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def default_data_root() -> Path:
    override = os.getenv("SECRETBASE_DESKTOP_DATA_ROOT")
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform.startswith("win"):
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            return (Path(local_app_data) / "SecretBase").resolve()

    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / "SecretBase").resolve()

    return (Path.home() / ".local" / "share" / "SecretBase").resolve()


def build_desktop_env(data_root: Path, port: int) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "SECRETBASE_MODE": "desktop",
        "HOST": "127.0.0.1",
        "PORT": str(port),
        "DATA_DIR": str(data_root / "data"),
        "VAULT_PATH": str(data_root / "data" / "secretbase.enc"),
        "BACKUP_DIR": str(data_root / "data" / "backups"),
        "LOG_DIR": str(data_root / "logs"),
        "SETTINGS_PATH": str(data_root / "settings.json"),
        "PYTHONPATH": str(BACKEND_DIR),
    })
    return env


def config_snapshot(data_root: Path, port: int) -> dict[str, str | int]:
    return {
        "mode": "desktop",
        "host": "127.0.0.1",
        "port": port,
        "data_root": str(data_root),
        "data_dir": str((data_root / "data").resolve()),
        "vault_path": str((data_root / "data" / "secretbase.enc").resolve()),
        "backup_dir": str((data_root / "data" / "backups").resolve()),
        "log_dir": str((data_root / "logs").resolve()),
        "settings_path": str((data_root / "settings.json").resolve()),
    }


def start_backend(env: dict[str, str], port: int) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=BACKEND_DIR,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def collect_output(process: subprocess.Popen[str], lines: deque[str]) -> threading.Thread:
    def reader() -> None:
        if process.stdout is None:
            return
        for line in process.stdout:
            lines.append(line.rstrip())

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    return thread


def wait_for_health(url: str, process: subprocess.Popen[str], timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def stop_backend(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def print_failure(lines: deque[str], log_dir: Path) -> None:
    print("SecretBase desktop backend failed to start.", file=sys.stderr)
    print(f"Log directory: {log_dir}", file=sys.stderr)
    if lines:
        print("Recent backend output:", file=sys.stderr)
        for line in list(lines)[-50:]:
            print(line, file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start SecretBase in local desktop mode.")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved desktop config as JSON and exit.")
    parser.add_argument("--no-browser", action="store_true", help="Start backend without opening the default browser.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_root = default_data_root()
    port = choose_free_port()
    snapshot = config_snapshot(data_root, port)

    if args.dry_run:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0

    env = build_desktop_env(data_root, port)
    process = start_backend(env, port)
    lines: deque[str] = deque(maxlen=200)
    collect_output(process, lines)
    url = f"http://127.0.0.1:{port}"

    def shutdown(_signum=None, _frame=None) -> None:
        stop_backend(process)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    if not wait_for_health(url, process):
        print_failure(lines, data_root / "logs")
        stop_backend(process)
        return 1

    print(f"SecretBase desktop backend ready: {url}", flush=True)
    print(f"Data directory: {data_root}", flush=True)
    print(f"Log directory: {data_root / 'logs'}", flush=True)

    if not args.no_browser:
        webbrowser.open(url)

    try:
        while process.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        stop_backend(process)
    return process.returncode or 0


if __name__ == "__main__":
    raise SystemExit(main())
