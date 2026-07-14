"""SupabaseGenerationRepository 통합 테스트 (실 DB 라운드트립).

DATABASE_URL 이 설정된 경우에만 실행한다(미설정 시 전체 skip — 오프라인/CI 안전).
넣은 행은 tearDown 에서 삭제해 DB 를 원상 복구한다.

실행:
    # apimgr 에서, .env 로 DATABASE_URL 주입한 상태
    DATABASE_URL="postgresql://postgres:...@db.<ref>.supabase.co:5432/postgres" \
        .venv/Scripts/python -m unittest tests.test_supabase_repository -v
"""

from __future__ import annotations

import os
import unittest
import uuid
from decimal import Decimal

from app.domain.enums import GenerationStatus, GenerationType, ProviderName
from app.domain.models import Generation

_DSN = os.environ.get("DATABASE_URL", "")


@unittest.skipUnless(_DSN, "실 DB 연결(DATABASE_URL) 미설정 — 통합 테스트 skip")
class TestSupabaseGenerationRepository(unittest.TestCase):
    def setUp(self) -> None:
        from app.repositories.supabase_generation_repository import (
            SupabaseGenerationRepository,
        )

        self.repo = SupabaseGenerationRepository(_DSN)
        self._ids: list[str] = []

    def tearDown(self) -> None:
        import psycopg

        with psycopg.connect(_DSN) as conn:
            for gid in self._ids:
                conn.execute("DELETE FROM public.generations WHERE id=%s", (uuid.UUID(gid),))

    def _new_generation(self) -> Generation:
        gid = str(uuid.uuid4())
        self._ids.append(gid)
        return Generation(
            id=gid,
            consultation_id=str(uuid.uuid4()),
            generation_type=GenerationType.VIDEO,
            provider=ProviderName.MOCK,
            status=GenerationStatus.CREATED,
            idempotency_key=f"itest-{gid}",
            input_asset_id=None,  # assets FK 회피
        )

    def test_save_then_get_roundtrip(self):
        gen = self._new_generation()
        self.repo.save(gen)
        got = self.repo.get(gen.id)
        self.assertIsNotNone(got)
        self.assertEqual(got.id, gen.id)
        self.assertEqual(got.status, GenerationStatus.CREATED)
        self.assertEqual(got.generation_type, GenerationType.VIDEO)
        self.assertEqual(got.provider, ProviderName.MOCK)

    def test_update_persists_all_fields(self):
        gen = self._new_generation()
        self.repo.save(gen)
        gen.status = GenerationStatus.SUBMITTED
        gen.provider = ProviderName.PIXVERSE
        gen.external_job_id = "ext-123"
        gen.estimated_cost_usd = Decimal("0.42")
        self.repo.update(gen)
        got = self.repo.get(gen.id)
        self.assertEqual(got.status, GenerationStatus.SUBMITTED)
        self.assertEqual(got.provider, ProviderName.PIXVERSE)
        self.assertEqual(got.external_job_id, "ext-123")
        self.assertEqual(got.estimated_cost_usd, Decimal("0.42"))

    def test_get_by_idempotency_key(self):
        gen = self._new_generation()
        self.repo.save(gen)
        got = self.repo.get_by_idempotency_key(gen.idempotency_key)
        self.assertIsNotNone(got)
        self.assertEqual(got.id, gen.id)

    def test_get_by_external_job_id(self):
        gen = self._new_generation()
        gen.external_job_id = f"ext-{gen.id}"
        self.repo.save(gen)
        self.repo.update(gen)
        got = self.repo.get_by_external_job_id("MOCK", gen.external_job_id)
        self.assertIsNotNone(got)
        self.assertEqual(got.id, gen.id)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.repo.get(str(uuid.uuid4())))


if __name__ == "__main__":
    unittest.main()
