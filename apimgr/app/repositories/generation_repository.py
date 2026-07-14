"""Generation 저장소 인터페이스 + 인메모리 구현.

⚠️ 인메모리는 단일 프로세스 스캐폴드/테스트용. 실 동시성 중복 방지는
DB `idempotency_key` UNIQUE 제약이 담당한다(규칙 §4.10).

값 의미론(중요): save/update 는 저장 시 **복사본**을 보관하고 get 계열은 **복사본**을 반환한다.
그래야 서비스가 로컬 객체를 mutate 해도 update() 를 호출해야만 저장소에 반영된다
(참조 공유로 인한 false green — "update 안 해도 통과" — 방지).

⚠️ `copy.copy`(얕은 복사)는 현재 Generation 필드가 전부 불변 타입(str/enum/Decimal/datetime/None)이라
안전하다. 향후 mutable 필드(list/dict)를 추가하면 하위구조 공유로 false green 이 재발하므로
`copy.deepcopy` 또는 `dataclasses.replace` 로 바꿔야 한다.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod

from app.domain.models import Generation


class GenerationRepository(ABC):
    @abstractmethod
    def save(self, generation: Generation) -> Generation:
        ...

    @abstractmethod
    def update(self, generation: Generation) -> Generation:
        """작업 전체를 영속한다(status 뿐 아니라 external_job_id·error_code·cost 등 모든 필드).

        실 DB 에서는 전체 컬럼 UPDATE. status 만 저장하면 external_job_id·error_code 가 유실된다.
        """
        ...

    @abstractmethod
    def get(self, generation_id: str) -> Generation | None:
        ...

    @abstractmethod
    def get_by_external_job_id(self, provider: str, external_job_id: str) -> Generation | None:
        ...

    @abstractmethod
    def get_by_idempotency_key(self, key: str) -> Generation | None:
        ...


class InMemoryGenerationRepository(GenerationRepository):
    def __init__(self) -> None:
        self._by_id: dict[str, Generation] = {}
        self._idem: dict[str, str] = {}  # idempotency_key -> generation_id

    def save(self, generation: Generation) -> Generation:
        # idempotency_key 는 신규일 때만 등록(원자적 setdefault — 실 DB 는 UNIQUE 제약).
        self._idem.setdefault(generation.idempotency_key, generation.id)
        self._by_id[generation.id] = copy.copy(generation)  # 복사본 보관
        return generation

    def update(self, generation: Generation) -> Generation:
        self._by_id[generation.id] = copy.copy(generation)  # 전체 객체 재저장(복사본)
        return generation

    def get(self, generation_id: str) -> Generation | None:
        gen = self._by_id.get(generation_id)
        return copy.copy(gen) if gen is not None else None

    def get_by_external_job_id(self, provider: str, external_job_id: str) -> Generation | None:
        for gen in self._by_id.values():
            if gen.provider.value == provider and gen.external_job_id == external_job_id:
                return copy.copy(gen)
        return None

    def get_by_idempotency_key(self, key: str) -> Generation | None:
        gen_id = self._idem.get(key)
        if gen_id is None:
            return None
        gen = self._by_id.get(gen_id)
        return copy.copy(gen) if gen is not None else None
