from pathlib import Path

from fastapi import FastAPI

from app.api.project_scope import scope_for
from app.api.services import Services
from app.core.models.run import RunScope
from app.settings import Settings
from tests.conftest import make_project
from tests.fakes import FakeSheetsGateway


def test_settings_defaults_for_the_worker() -> None:
    settings = Settings(_env_file=None)

    assert settings.case_timeout_seconds == 120
    assert settings.step_timeout_ms == 10_000
    assert settings.app_start_timeout_seconds == 120
    assert settings.max_cases_per_run == 200
    assert settings.artifacts_dir == Path("artifacts")
    assert settings.worker_config_path == Path("worker-projects.json")


def test_project_scope_exposes_run_repositories(
    app: FastAPI, gateway: FakeSheetsGateway
) -> None:
    services: Services = app.state.services
    project = make_project(services.projects, services.members, gateway)

    scope = scope_for(services, project)

    run = scope.runs.create(triggered_by="a@x.com", scope=RunScope(), branch="main", total=0)
    assert scope.runs.get(run.id) is not None
    assert scope.results.list_for_run(run.id) == []
