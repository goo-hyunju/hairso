"""Generation 저장소의 Supabase(psycopg 동기) 구현.

동기 인터페이스(GenerationRepository)를 그대로 구현한다 — Service/Worker/Webhook 호출부 무변경.
deps 가 DATABASE_URL 존재 시 이 구현을, 없으면 InMemory(스캐폴드)를 주입한다.

설계 메모:
- 매 메서드에서 새 연결(`with psycopg.connect`)을 연다 — 스캐폴드 단순화. 부하 증가 시 psycopg_pool 로 교체.
- idempotency 동시성 최종 방어는 DB `generations.idempotency_key` UNIQUE 제약(§4.10).
  save 는 UniqueViolation 을 그대로 전파한다(선조회만으로 막았다고 판단하지 않음 — §4.10).
- uuid 컬럼(id/consultation_id/batch_id/input_asset_id/output_asset_id)은 psycopg 가 text→uuid 를
  암묵 캐스팅하지 않으므로 `uuid.UUID` 객체로 변환해 바인딩한다.
- enum 은 저장 시 `.value`(문자열), 조회 시 enum 으로 복원한다.
"""

from __future__ import annotations

import uuid

import psycopg
from psycopg.rows import dict_row

from app.domain.enums import ErrorCode, GenerationStatus, GenerationType, ProviderName
from app.domain.models import Generation
from app.repositories.generation_repository import GenerationRepository

_SELECT_COLUMNS = (
    "id, consultation_id, generation_type, provider, status, idempotency_key, "
    "model, batch_id, external_job_id, ai_trace_id, input_asset_id, output_asset_id, "
    "prompt, negative_prompt, estimated_cost_usd, actual_cost_usd, error_code, "
    "error_message, share_token, created_at, submitted_at, completed_at"
)


def _uid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None


def _row_to_generation(row: dict) -> Generation:
    """DB row(dict) → Generation dataclass. 문자열 enum 값을 enum 으로 복원한다."""
    return Generation(
        id=str(row["id"]),
        consultation_id=str(row["consultation_id"]) if row["consultation_id"] is not None else "",
        generation_type=GenerationType(row["generation_type"]),
        provider=ProviderName(row["provider"]),
        status=GenerationStatus(row["status"]),
        idempotency_key=row["idempotency_key"],
        model=row["model"],
        batch_id=str(row["batch_id"]) if row["batch_id"] is not None else None,
        external_job_id=row["external_job_id"],
        ai_trace_id=row["ai_trace_id"],
        input_asset_id=str(row["input_asset_id"]) if row["input_asset_id"] is not None else None,
        output_asset_id=str(row["output_asset_id"]) if row["output_asset_id"] is not None else None,
        prompt=row["prompt"],
        negative_prompt=row["negative_prompt"],
        estimated_cost_usd=row["estimated_cost_usd"],
        actual_cost_usd=row["actual_cost_usd"],
        error_code=ErrorCode(row["error_code"]) if row["error_code"] is not None else None,
        error_message=row["error_message"],
        share_token=row["share_token"],
        created_at=row["created_at"],
        submitted_at=row["submitted_at"],
        completed_at=row["completed_at"],
    )


def _to_params(g: Generation) -> dict:
    """Generation → SQL 바인딩 파라미터. enum→value, uuid 문자열→UUID 객체."""
    return {
        "id": _uid(g.id),
        "consultation_id": _uid(g.consultation_id) if g.consultation_id else None,
        "generation_type": g.generation_type.value,
        "provider": g.provider.value,
        "status": g.status.value,
        "idempotency_key": g.idempotency_key,
        "model": g.model,
        "batch_id": _uid(g.batch_id),
        "external_job_id": g.external_job_id,
        "ai_trace_id": g.ai_trace_id,
        "input_asset_id": _uid(g.input_asset_id),
        "output_asset_id": _uid(g.output_asset_id),
        "prompt": g.prompt,
        "negative_prompt": g.negative_prompt,
        "estimated_cost_usd": g.estimated_cost_usd,
        "actual_cost_usd": g.actual_cost_usd,
        "error_code": g.error_code.value if g.error_code is not None else None,
        "error_message": g.error_message,
        "share_token": g.share_token,
        "created_at": g.created_at,
        "submitted_at": g.submitted_at,
        "completed_at": g.completed_at,
    }


class SupabaseGenerationRepository(GenerationRepository):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def save(self, generation: Generation) -> Generation:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            conn.execute(
                """
                INSERT INTO public.generations
                    (id, consultation_id, generation_type, provider, status, idempotency_key,
                     model, batch_id, external_job_id, ai_trace_id, input_asset_id, output_asset_id,
                     prompt, negative_prompt, estimated_cost_usd, actual_cost_usd, error_code,
                     error_message, share_token, created_at, submitted_at, completed_at)
                VALUES
                    (%(id)s, %(consultation_id)s, %(generation_type)s, %(provider)s, %(status)s,
                     %(idempotency_key)s, %(model)s, %(batch_id)s, %(external_job_id)s, %(ai_trace_id)s,
                     %(input_asset_id)s, %(output_asset_id)s, %(prompt)s, %(negative_prompt)s,
                     %(estimated_cost_usd)s, %(actual_cost_usd)s, %(error_code)s, %(error_message)s,
                     %(share_token)s, %(created_at)s, %(submitted_at)s, %(completed_at)s)
                """,
                _to_params(generation),
            )
        return generation

    def update(self, generation: Generation) -> Generation:
        # 전체 컬럼 UPDATE(§ repo 계약: status 뿐 아니라 external_job_id·cost 등 모두 영속).
        # idempotency_key·created_at 은 불변이라 갱신하지 않는다. updated_at 은 now().
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            conn.execute(
                """
                UPDATE public.generations SET
                    consultation_id=%(consultation_id)s, generation_type=%(generation_type)s,
                    provider=%(provider)s, status=%(status)s, model=%(model)s, batch_id=%(batch_id)s,
                    external_job_id=%(external_job_id)s, ai_trace_id=%(ai_trace_id)s,
                    input_asset_id=%(input_asset_id)s, output_asset_id=%(output_asset_id)s,
                    prompt=%(prompt)s, negative_prompt=%(negative_prompt)s,
                    estimated_cost_usd=%(estimated_cost_usd)s, actual_cost_usd=%(actual_cost_usd)s,
                    error_code=%(error_code)s, error_message=%(error_message)s,
                    share_token=%(share_token)s, submitted_at=%(submitted_at)s,
                    completed_at=%(completed_at)s, updated_at=now()
                WHERE id=%(id)s
                """,
                _to_params(generation),
            )
        return generation

    def get(self, generation_id: str) -> Generation | None:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                f"SELECT {_SELECT_COLUMNS} FROM public.generations WHERE id=%s",
                (_uid(generation_id),),
            ).fetchone()
        return _row_to_generation(row) if row is not None else None

    def get_by_external_job_id(
        self, provider: str, external_job_id: str
    ) -> Generation | None:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                f"SELECT {_SELECT_COLUMNS} FROM public.generations "
                "WHERE provider=%s AND external_job_id=%s",
                (provider, external_job_id),
            ).fetchone()
        return _row_to_generation(row) if row is not None else None

    def get_by_idempotency_key(self, key: str) -> Generation | None:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                f"SELECT {_SELECT_COLUMNS} FROM public.generations WHERE idempotency_key=%s",
                (key,),
            ).fetchone()
        return _row_to_generation(row) if row is not None else None
