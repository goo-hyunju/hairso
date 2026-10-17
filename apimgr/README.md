# apimgr — Hairso Studio Backend (FastAPI)

AI 쇼츠 제작 스튜디오의 백엔드. 컨벤션: [`docs/conventions.md`](./docs/conventions.md) · API 계약: [`docs/api-contract.md`](./docs/api-contract.md) · DB: [`docs/DB_SCHEMA.md`](./docs/DB_SCHEMA.md).

## 빠른 시작
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Windows (macOS/Linux: .venv/bin/python)
.venv/Scripts/python -m pytest -q                  # pytest
.venv/Scripts/python main.py                       # 개발 서버 → http://127.0.0.1:8000/docs
```

## 검증 (2026-10-17 실행)
- `python -m compileall app main.py tests scripts` — OK
- `pytest -q` — **107 passed, 5 skipped**(Supabase 라운드트립 5건은 `DATABASE_URL` 미설정 시 skip)
- 설치 버전: fastapi 0.139.0 · pydantic 2.13.4

## 구조
`app/{core,domain,schemas,services,repositories,providers,workers,api}` + `main.py` + `tests/` + `db/`(schema.sql 참고용 + migrations/) + `contract/enums.json`(계약 정본).

기본 Provider 는 Mock(외부 API·키 불필요). opt-in: `DEFAULT_STUDIO_DRAFT_PROVIDER=OLLAMA`(로컬 Ollama 초안, 실패 시 Mock fallback), `DEFAULT_IMAGE_PROVIDER=LOCAL_SD` · `DEFAULT_VIDEO_PROVIDER=SELF_HOSTED_WAN`(로컬 `ml/serve.py`), `DATABASE_URL`(Supabase Postgres 저장소), `ASSET_STORE_BACKEND=SUPABASE`. 실 외부 Provider(PixVerse·fal·Wan Cloud·Gemini)·Worker 큐·크레딧은 로드맵([`docs/development-plan.md`](./docs/development-plan.md)).
