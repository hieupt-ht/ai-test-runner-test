"""Dựng các repository làm việc trên Sheet riêng của một dự án."""

from dataclasses import dataclass

from app.api.services import Services
from app.core.models.project import Project
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.screens import ScreenRepository
from app.core.repositories.test_cases import TestCaseRepository


@dataclass
class ProjectScope:
    project: Project
    screens: ScreenRepository
    assignments: AssignmentRepository
    test_cases: TestCaseRepository
    audit_log: AuditLogRepository  # nhật ký riêng của dự án (tab AuditLog trong Sheet dự án)


def scope_for(services: Services, project: Project) -> ProjectScope:
    sheet = project.spreadsheet_id
    return ProjectScope(
        project=project,
        screens=ScreenRepository(
            services.gateway,
            sheet,
            services.redis,
            project.id,
            lock_wait_seconds=services.lock_wait_seconds,
        ),
        assignments=AssignmentRepository(
            services.gateway,
            sheet,
            services.redis,
            project.id,
            lock_wait_seconds=services.lock_wait_seconds,
        ),
        test_cases=TestCaseRepository(
            services.gateway,
            sheet,
            services.redis,
            project.id,
            lock_wait_seconds=services.lock_wait_seconds,
        ),
        audit_log=AuditLogRepository(services.gateway, sheet),
    )
