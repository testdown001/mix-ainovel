"""Project provenance is set by trusted creation paths, independently of AI usage."""

from enum import Enum


class ProjectSource(str, Enum):
    USER = "user"
    SYSTEM = "system"
    AI_TEST = "ai_test"


ADMIN_DELETABLE_SOURCES = frozenset({ProjectSource.SYSTEM.value, ProjectSource.AI_TEST.value})
