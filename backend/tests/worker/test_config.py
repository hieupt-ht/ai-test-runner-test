import json
from pathlib import Path

import pytest

from app.core.models.test_case import AutoType
from app.worker.config import WorkerConfigError, load_project_config

PASSWORD = "s3cret-pass-123"


def write_config(path: Path, projects: dict[str, object]) -> Path:
    file = path / "worker-projects.json"
    file.write_text(json.dumps(projects, ensure_ascii=False), encoding="utf-8")
    return file


def good_project(app_dir: Path) -> dict[str, object]:
    return {
        "app_path": str(app_dir),
        "start_command": "npm run dev",
        "app_url": "http://localhost:3000",
        "test_email": "qa@x.com",
        "test_password": PASSWORD,
        "login_steps": [
            {"type": "goto", "value": "/login"},
            {"type": "fill", "target": {"by": "label", "value": "Email"}, "value": "{email}"},
            {"type": "click", "target": {"by": "text", "value": "Đăng nhập"}},
        ],
    }


def test_loads_project_config(tmp_path: Path) -> None:
    file = write_config(tmp_path, {"PRJ-0001": good_project(tmp_path)})

    config = load_project_config(file, "PRJ-0001")

    assert config.start_command == "npm run dev"
    assert config.app_url == "http://localhost:3000"
    assert config.test_email == "qa@x.com"
    assert [step.type for step in config.login_steps] == [
        AutoType.GOTO,
        AutoType.FILL,
        AutoType.CLICK,
    ]


def test_login_steps_default_to_empty(tmp_path: Path) -> None:
    project = good_project(tmp_path)
    del project["login_steps"]
    file = write_config(tmp_path, {"PRJ-0001": project})

    assert load_project_config(file, "PRJ-0001").login_steps == []


def test_missing_file_message_names_the_file(tmp_path: Path) -> None:
    with pytest.raises(WorkerConfigError, match=r"worker-projects\.json"):
        load_project_config(tmp_path / "worker-projects.json", "PRJ-0001")


def test_missing_project_message_names_project_id(tmp_path: Path) -> None:
    file = write_config(tmp_path, {"PRJ-0002": good_project(tmp_path)})

    with pytest.raises(WorkerConfigError, match="PRJ-0001"):
        load_project_config(file, "PRJ-0001")


def test_invalid_json_is_config_error(tmp_path: Path) -> None:
    file = tmp_path / "worker-projects.json"
    file.write_text("{ không phải json", encoding="utf-8")

    with pytest.raises(WorkerConfigError):
        load_project_config(file, "PRJ-0001")


def test_missing_app_path_directory_is_config_error(tmp_path: Path) -> None:
    project = good_project(tmp_path / "khong-ton-tai")
    file = write_config(tmp_path, {"PRJ-0001": project})

    with pytest.raises(WorkerConfigError, match="app_path"):
        load_project_config(file, "PRJ-0001")


def test_error_messages_never_contain_password(tmp_path: Path) -> None:
    project = good_project(tmp_path)
    del project["app_url"]
    file = write_config(tmp_path, {"PRJ-0001": project})

    with pytest.raises(WorkerConfigError) as error:
        load_project_config(file, "PRJ-0001")

    assert "app_url" in str(error.value)
    assert PASSWORD not in str(error.value)


def test_login_steps_are_validated_as_auto_steps(tmp_path: Path) -> None:
    project = good_project(tmp_path)
    project["login_steps"] = [{"type": "click"}]  # thiếu phần tử cần bấm
    file = write_config(tmp_path, {"PRJ-0001": project})

    with pytest.raises(WorkerConfigError, match="login_steps"):
        load_project_config(file, "PRJ-0001")
