"""apimgr — Hairso Studio 백엔드 (FastAPI).

계층 구조 (의존 방향은 단방향):
    api  ->  services  ->  repositories / providers  ->  external
    (schemas)                (domain)
    core 는 leaf — app 내 어떤 모듈도 import 하지 않는다.

2층 분리:
    - stdlib 순수 계층: core / domain / providers / repositories / services 의 순수 로직
      (fastapi·pydantic 미의존 → 네트워크 없이 unittest 로 검증 가능)
    - deps 계층: schemas(pydantic) / api(fastapi) / main
"""
