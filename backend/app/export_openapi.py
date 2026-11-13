"""Ghi mô tả OpenAPI ra file để frontend sinh kiểu TypeScript (không cần chạy server).

Cách dùng: uv run python -m app.export_openapi ../frontend/lib/api/openapi.json
"""

import json
import sys
from pathlib import Path

from app.main import create_app
from app.settings import Settings


def main() -> None:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    schema = create_app(Settings(session_secret="export-only")).openapi()
    output.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)  # chỉ in đường dẫn: console Windows có thể không in được tiếng Việt


if __name__ == "__main__":
    main()
