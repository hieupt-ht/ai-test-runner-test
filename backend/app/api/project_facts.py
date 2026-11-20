"""Lấy `ProjectFacts` của một project qua cache."""

from app.api.project_scope import ProjectScope
from app.api.services import Services
from app.core.models.stats import ProjectFacts
from app.core.services.stats import facts_from
from app.core.stats_cache import FactsCache


def load_facts(services: Services, scope: ProjectScope) -> ProjectFacts:
    cache = FactsCache(services.redis, scope.project.id, services.stats_cache_ttl_seconds)
    return cache.read(lambda: facts_from(scope.test_cases.list_all(), scope.results.list_all()))
