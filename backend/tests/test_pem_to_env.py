from pathlib import Path

from app.core.github.client import normalize_private_key
from app.tools.pem_to_env import pem_to_env_value

PEM = "-----BEGIN RSA PRIVATE KEY-----\nAAA\nBBB\n-----END RSA PRIVATE KEY-----\n"


def test_pem_becomes_one_quoted_line(tmp_path: Path) -> None:
    pem_file = tmp_path / "key.pem"
    pem_file.write_text(PEM, encoding="utf-8")

    value = pem_to_env_value(pem_file)

    assert "\n" not in value
    assert value.startswith("'-----BEGIN") and value.endswith("KEY-----'")
    # Backend đọc lại phải ra đúng nội dung khoá ban đầu
    assert normalize_private_key(value) == PEM.strip()


def test_windows_line_endings_are_handled(tmp_path: Path) -> None:
    pem_file = tmp_path / "key.pem"
    pem_file.write_bytes(PEM.replace("\n", "\r\n").encode())

    assert normalize_private_key(pem_to_env_value(pem_file)) == PEM.strip()
