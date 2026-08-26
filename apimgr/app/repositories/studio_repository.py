"""Studio project 저장소 인터페이스 + 인메모리 구현.

인메모리는 테스트/Mock 개발 전용이다. 실 동시성, render 중복 방지, version 충돌은 DB UNIQUE/락이
최종 방어선이다.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod

from app.domain.studio import StudioProject


class StudioRepository(ABC):
    @abstractmethod
    def save(self, project: StudioProject) -> StudioProject:
        ...

    @abstractmethod
    def update(self, project: StudioProject) -> StudioProject:
        ...

    @abstractmethod
    def get(self, project_id: str) -> StudioProject | None:
        ...


class InMemoryStudioRepository(StudioRepository):
    def __init__(self) -> None:
        self._by_id: dict[str, StudioProject] = {}

    def save(self, project: StudioProject) -> StudioProject:
        self._by_id[project.id] = copy.deepcopy(project)
        return copy.deepcopy(project)

    def update(self, project: StudioProject) -> StudioProject:
        self._by_id[project.id] = copy.deepcopy(project)
        return copy.deepcopy(project)

    def get(self, project_id: str) -> StudioProject | None:
        project = self._by_id.get(project_id)
        return copy.deepcopy(project) if project is not None else None
