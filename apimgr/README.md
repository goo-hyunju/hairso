# apimgr — HairView AI Backend (FastAPI)

AI 헤어스타일 상담·영상 시뮬레이션 백엔드 스캐폴드. 진입점 문서: [`CLAUDE.md`](./CLAUDE.md).

## 빠른 시작
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Windows (macOS/Linux: .venv/bin/python)
.venv/Scripts/python -m pytest -q                  # pytest
.venv/Scripts/python -m uvicorn main:app --reload  # 개발 서버 → http://127.0.0.1:8000/docs
```

## 검증 (설치 시점 실측)
- `python -m compileall app main.py tests` — OK
- `pytest -q` — **56 passed, 5 skipped**
- `unittest discover` — **61 ran, 5 skipped**
- FastAPI TestClient 스모크 — health/analyze/202/status/idempotent/404 통과
- 설치 버전: fastapi 0.139.0 · pydantic 2.13.4 · pytest 9.1.1

## 구조
`app/{core,domain,schemas,services,repositories,providers,workers,api}` + `main.py` + `tests/` + `db/schema.sql`(참고) + `contract/enums.json`(계약 정본).

기본 Provider 는 Mock(외부 API·키 불필요). Studio draft는 `DEFAULT_STUDIO_DRAFT_PROVIDER=OLLAMA`와
`OLLAMA_STUDIO_DRAFT_MODEL`을 설정하면 backend-only 로컬 Ollama 초안 생성을 사용할 수 있고,
실패 시 Mock 초안으로 fallback한다. 실 영상 연동·실 DB 는 로드맵([`docs/development-plan.md`](./docs/development-plan.md)).
