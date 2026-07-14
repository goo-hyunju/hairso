# HairView AI

미용실 고객의 얼굴은 유지하고 헤어스타일만 적용한 예상 이미지·영상을 생성하는 **AI 미용 상담 서비스**(스캐폴드).

## 저장소 구성
| 경로 | 역할 | 스택 | 검증 |
|---|---|---|---|
| [`hairsoui/`](./hairsoui) | FE | Next.js 15 · React 19 · TS strict · Tailwind v4 · Zod | typecheck 0 · test 12 · build 0 · lint 0 |
| [`apimgr/`](./apimgr) | BE | Python 3.12 · FastAPI · Pydantic v2 | compile OK · pytest 44 · TestClient 스모크 |
| [`docs/`](./docs) | 교차 문서 | — | — |

> BE 는 Python·FastAPI(루트 CLAUDE.md 규칙 우선 — 기획서의 TS BE 서술 미채택). 두 저장소는 독립.

## 문서
- 제품/설계: [`docs/PRD.md`](./docs/PRD.md) · [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) · [`docs/PRIVACY.md`](./docs/PRIVACY.md) · [`docs/SECURITY.md`](./docs/SECURITY.md) · [`docs/PROMPT_GUIDE.md`](./docs/PROMPT_GUIDE.md) · [`docs/TEST_SCENARIOS.md`](./docs/TEST_SCENARIOS.md) · [`docs/TASKS.md`](./docs/TASKS.md)
- **산출 상태(3구간 라벨):** [`docs/LABELS.md`](./docs/LABELS.md) ← 무엇이 구현·검증완료 / Mock / 로드맵인지.
- 진입점: `hairsoui/CLAUDE.md` · `apimgr/CLAUDE.md`.

## 빠른 시작
```bash
# BE
cd apimgr && python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]" && .venv/Scripts/python -m pytest -q
# FE
cd hairsoui && npm install && npm run typecheck && npm run test && npm run build
```

## 핵심 특성
- 얼굴 정체성 유지 · 헤어만 변경. 연예인 이름 프롬프트 제거. 결과는 시술 보장 아님.
- 외부 AI 는 BE 경유(FE 직접 호출 금지). 비동기 202+job_id. Idempotency·상태 전이 단일 관리. 기본 Mock Provider.
- 하이브리드 반응형(웹+모바일 한 코드베이스, 네이티브 아님).

## 주의
실 외부 AI·실 DB·카메라 실동작 등은 **로드맵**(미구현). 상세·미검증 외부 사실은 [`docs/LABELS.md`](./docs/LABELS.md) 참조.
