from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from pathlib import Path

try:
    from .runtime import (
        SOURCE_ROOT as PROJECT_ROOT,
        build_desktop_env,
        bundled_backend_dir,
        choose_free_port,
        prepare_data_root,
        resolve_data_root,
        snapshot_json,
        wait_for_health,
    )
except ImportError:
    from runtime import (
        SOURCE_ROOT as PROJECT_ROOT,
        build_desktop_env,
        bundled_backend_dir,
        choose_free_port,
        prepare_data_root,
        resolve_data_root,
        snapshot_json,
        wait_for_health,
    )


BACKEND_DIR = bundled_backend_dir()


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
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0,
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
    parser.add_argument("--data-root", help="Override the local SecretBase data directory for this launch.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_root = resolve_data_root(args.data_root)
    port = choose_free_port()
    if args.dry_run:
        print(snapshot_json(data_root, port))
        return 0

    prepare_data_root(data_root)
    env = build_desktop_env(data_root, port)
    process = start_backend(env, port)
    lines: deque[str] = deque(maxlen=200)
    collect_output(process, lines)
    url = f"http://127.0.0.1:{port}"

    def shutdown(_signum=None, _frame=None) -> None:
        stop_backend(process)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, shutdown)

    if not wait_for_health(url, timeout=15.0, is_running=lambda: process.poll() is None):
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
