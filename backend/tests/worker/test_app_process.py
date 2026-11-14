import socket
import sys
import time
from pathlib import Path

import psutil
import pytest

from app.worker.app_process import AppStartError, running_app
from app.worker.config import ProjectWorkerConfig

PYTHON = f'"{sys.executable}"'


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def is_up(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def make_config(tmp_path: Path, command: str, port: int) -> ProjectWorkerConfig:
    return ProjectWorkerConfig(
        app_path=str(tmp_path),
        start_command=command,
        app_url=f"http://127.0.0.1:{port}",
        test_email="qa@x.com",
        test_password="x",
    )


def write_script(tmp_path: Path, name: str, code: str) -> str:
    path = tmp_path / name
    path.write_text(code, encoding="utf-8")
    return f'{PYTHON} "{path}"'


SERVER = """
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
HTTPServer(("127.0.0.1", int(sys.argv[1])), SimpleHTTPRequestHandler).serve_forever()
"""


def test_app_is_reachable_inside_block_and_stopped_after(tmp_path: Path) -> None:
    port = free_port()
    command = write_script(tmp_path, "server.py", SERVER) + f" {port}"

    with running_app(make_config(tmp_path, command, port), timeout_seconds=30):
        assert is_up(port)

    time.sleep(0.5)
    assert not is_up(port)


def test_child_processes_are_killed(tmp_path: Path) -> None:
    port = free_port()
    pid_file = tmp_path / "child.pid"
    code = f"""
import subprocess, sys
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
open(r"{pid_file}", "w").write(str(child.pid))
from http.server import HTTPServer, SimpleHTTPRequestHandler
HTTPServer(("127.0.0.1", int(sys.argv[1])), SimpleHTTPRequestHandler).serve_forever()
"""
    command = write_script(tmp_path, "parent.py", code) + f" {port}"

    with running_app(make_config(tmp_path, command, port), timeout_seconds=30):
        child_pid = int(pid_file.read_text())
        assert psutil.pid_exists(child_pid)

    time.sleep(0.5)
    assert not psutil.pid_exists(child_pid)


def test_command_that_exits_immediately_raises_app_start_error(tmp_path: Path) -> None:
    command = write_script(tmp_path, "boom.py", "print('app boom'); raise SystemExit(3)")

    with (
        pytest.raises(AppStartError, match="app boom"),
        running_app(make_config(tmp_path, command, free_port()), timeout_seconds=30),
    ):
        pytest.fail("không được vào khối này")


def test_never_ready_raises_after_timeout_and_kills_process(tmp_path: Path) -> None:
    pid_file = tmp_path / "sleeper.pid"
    code = f"""
import os, time
open(r"{pid_file}", "w").write(str(os.getpid()))
time.sleep(600)
"""
    command = write_script(tmp_path, "sleeper.py", code)
    started = time.monotonic()

    with (
        pytest.raises(AppStartError, match="chưa sẵn sàng"),
        running_app(make_config(tmp_path, command, free_port()), timeout_seconds=1),
    ):
        pytest.fail("không được vào khối này")

    assert time.monotonic() - started < 15
    time.sleep(0.5)
    assert not psutil.pid_exists(int(pid_file.read_text()))


def test_port_already_in_use_raises(tmp_path: Path) -> None:
    code = """
import socket, sys, time
server = socket.socket()
server.bind(("127.0.0.1", int(sys.argv[1])))
server.listen()
time.sleep(600)
"""
    command = write_script(tmp_path, "bind.py", code)

    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = int(occupied.getsockname()[1])
        with (
            pytest.raises(AppStartError),
            running_app(make_config(tmp_path, f"{command} {port}", port), timeout_seconds=30),
        ):
            pytest.fail("không được vào khối này")
