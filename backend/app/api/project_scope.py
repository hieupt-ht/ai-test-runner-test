"""Dựng các repository làm việc trên Sheet riêng của một dự án."""

from dataclasses import dataclass

from app.api.services import Services
from app.core.models.project import Project
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.modules import ModuleAssignmentRepository, ModuleRepository
from app.core.repositories.runs import ResultRepository, RunRepository
from app.core.repositories.screens import ScreenRepository
from app.core.repositories.test_cases import TestCaseRepository
from app.core.services.module_work import ModuleWorkService
from app.core.services.notify import Notifier


@dataclass
class ProjectScope:
    project: Project
    screens: ScreenRepository
    assignments: AssignmentRepository
    test_cases: TestCaseRepository
    audit_log: AuditLogRepository  # nhật ký riêng của dự án (tab AuditLog trong Sheet dự án)
    runs: RunRepository
    results: ResultRepository
    modules: ModuleRepository
    module_assignments: ModuleAssignmentRepository


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
            cache_ttl_seconds=services.sheet_cache_ttl_seconds,
        ),
        assignments=AssignmentRepository(
            services.gateway,
            sheet,
            services.redis,
            project.id,
            lock_wait_seconds=services.lock_wait_seconds,
            cache_ttl_seconds=services.sheet_cache_ttl_seconds,
        ),
        test_cases=TestCaseRepository(
            services.gateway,
            sheet,
            services.redis,
            project.id,
            lock_wait_seconds=services.lock_wait_seconds,
            cache_ttl_seconds=services.sheet_cache_ttl_seconds,
        ),
        audit_log=AuditLogRepository(services.gateway, sheet),
        runs=RunRepository(
            services.gateway,
            sheet,
            services.redis,
            project.id,
            lock_wait_seconds=services.lock_wait_seconds,
        ),
        results=ResultRepository(
            services.gateway, sheet, redis=services.redis, project_id=project.id
        ),
        modules=ModuleRepository(
            services.gateway,
            sheet,
            services.redis,
            project.id,
            lock_wait_seconds=services.lock_wait_seconds,
            cache_ttl_seconds=services.sheet_cache_ttl_seconds,
        ),
        module_assignments=ModuleAssignmentRepository(
            services.gateway,
            sheet,
            services.redis,
            project.id,
            lock_wait_seconds=services.lock_wait_seconds,
            cache_ttl_seconds=services.sheet_cache_ttl_seconds,
        ),
    )


def module_work_for(services: Services, scope: ProjectScope) -> ModuleWorkService:
    """Dựng ModuleWorkService trên đúng các repository của `scope` (khoá lồng được)."""
    return ModuleWorkService(
        project_id=scope.project.id,
        modules=scope.modules,
        screens=scope.screens,
        assignments=scope.assignments,
        module_assignments=scope.module_assignments,
        test_cases=scope.test_cases,
        members=services.members,
        users=services.users,
        audit_log=scope.audit_log,
        notifier=Notifier(services.notifications),
    )
