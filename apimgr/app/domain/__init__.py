"""domain — 순수 도메인 계층 (enum·모델·상태머신·에러코드).

stdlib 만 사용(fastapi·pydantic 미의존) → 네트워크 없이 unittest 로 검증 가능.
domain 은 core 만 import 한다. api/services/providers/repositories 를 import 하지 않는다.
(규칙: `grep -E "from app.(api|services)" app/domain` == 0)
"""
