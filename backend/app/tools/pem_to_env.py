"""In private key của GitHub App ra dạng một dòng để dán vào .env.

Cách dùng (chạy trong thư mục backend):
    uv run python -m app.tools.pem_to_env duong-dan/toi/file.pem

Rồi dán nguyên dòng in ra vào sau GITHUB_APP_PRIVATE_KEY=
"""

import sys
from pathlib import Path


def pem_to_env_value(pem_file: Path) -> str:
    text = pem_file.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    one_line = text.replace("\n", "\\n")  # xuống dòng thật → hai ký tự \ và n
    return f"'{one_line}'"


def main() -> None:
    if len(sys.argv) != 2:
        print("Cách dùng: uv run python -m app.tools.pem_to_env <file.pem>")
        raise SystemExit(1)
    print(pem_to_env_value(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
