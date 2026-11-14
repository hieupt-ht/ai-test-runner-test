"""Bật app của dự án để test, và chắc chắn tắt hết khi xong.

`running_app` chạy `start_command` trong `app_path`, chờ `app_url` trả lời, rồi nhường chỗ cho
khối `with`. Thoát khối (kể cả khi lỗi) thì tắt CẢ CÂY tiến trình: `npm run dev` thường sinh ra
nhiều tiến trình con, tắt mỗi tiến trình cha sẽ để sót app chạy ngầm.
"""

import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import IO

import httpx
import psutil

from app.worker.config import ProjectWorkerConfig

POLL_SECONDS = 0.5
OUTPUT_TAIL_LINES = 20


class AppStartError(Exception):
    """App không lên được: lệnh thoát sớm, quá giờ chờ, hoặc cổng đã bị chiếm."""


def _tail(output: IO[bytes]) -> str:
    output.flush()
    output.seek(0)
    lines = output.read().decode("utf-8", errors="replace").splitlines()
    return "\n".join(lines[-OUTPUT_TAIL_LINES:])


def _kill_tree(process: subprocess.Popen[bytes]) -> None:
    try:
        parent = psutil.Process(process.pid)
    except psutil.NoSuchProcess:
        return
    victims = [*parent.children(recursive=True), parent]
    for victim in victims:
        try:
            victim.kill()
        except psutil.NoSuchProcess:
            continue
    psutil.wait_procs(victims, timeout=10)


def _is_ready(url: str) -> bool:
    try:
        return httpx.get(url, timeout=2, follow_redirects=False).status_code < 500
    except httpx.HTTPError:
        return False


@contextmanager
def running_app(config: ProjectWorkerConfig, *, timeout_seconds: float) -> Iterator[None]:
    # Đã có app trả lời ở địa chỉ này (bản cũ còn sót, app bạn tự bật, hay app khác) thì lệnh mới
    # sẽ báo cổng bận mà ta lại tưởng "đã sẵn sàng" và chạy test nhầm vào app đó.
    if _is_ready(config.app_url):
        raise AppStartError(
            f"Đã có một app khác đang trả lời tại {config.app_url}. "
            "Hãy tắt nó trước khi chạy (hoặc đổi cổng của app cần test)."
        )
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(  # noqa: S602 - lệnh do chủ máy khai báo trong file cấu hình
            config.start_command,
            shell=True,
            cwd=config.app_path,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_until_ready(process, config.app_url, timeout_seconds, output)
            yield
        finally:
            _kill_tree(process)


def _wait_until_ready(
    process: subprocess.Popen[bytes], url: str, timeout_seconds: float, output: IO[bytes]
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        exit_code = process.poll()
        if exit_code is not None:
            raise AppStartError(
                f"Lệnh chạy app đã thoát (mã {exit_code}) trước khi app sẵn sàng.\n{_tail(output)}"
            )
        if _is_ready(url):
            return
        if time.monotonic() >= deadline:
            raise AppStartError(
                f"App chưa sẵn sàng tại {url} sau {timeout_seconds:g} giây.\n{_tail(output)}"
            )
        time.sleep(POLL_SECONDS)
