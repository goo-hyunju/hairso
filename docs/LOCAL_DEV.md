# 로컬 개발 실행 — FE ↔ BE 통합 배선 (검증본)

hairso 를 로컬에서 BE(apimgr) + FE(hairsoui) 함께 띄우는 단일 안내다.
아래 배선은 **실제 왕복(202 → 상태폴링 → SUCCEEDED)까지 실행해 검증**했다.

## 포트·경로 계약 (고정값)

| 항목 | 값 | 근거 |
| --- | --- | --- |
| BE(apimgr) 포트 | **8000** | `hairsoui/next.config.mjs` 프록시 대상이 `http://127.0.0.1:8000` (uvicorn 기본) |
| FE(hairsoui) 포트 | **3000** | `next dev` 기본 |
| BE API prefix | `/api/v1/*` | 라우터 prefix (`app/api/v1/generations.py` 등) |
| FE 요청 경로 | `/api/v1/*` | `src/lib/api/generations.ts` — BE 와 동일 |

## 브라우저 → BE 연결 방식: **Next 프록시 (CORS 미사용)**

```
브라우저 → FE(:3000) /api/*  ──[next.config rewrites]──▶  BE(:8000) /api/*
```

- `next.config.mjs` 의 `rewrites()` 가 `/api/:path*` 를 `http://127.0.0.1:8000/api/:path*` 로 서버사이드 전달한다.
- 브라우저 입장에선 **same-origin(:3000)** 이므로 **CORS 설정이 필요 없다.** BE 에 CORS 미들웨어를 두지 않는 것은 의도된 설계다.
- 프록시 대상 포트는 `API_PROXY_TARGET` env 로 바꿀 수 있다(기본 `http://127.0.0.1:8000`).
- **운영(production)은 이 프록시가 아니라 실제 게이트웨이/도메인**을 쓴다. 그때 FE 가 BE 를 다른 오리진으로 직접 호출한다면 그 시점에 BE CORS 또는 동일 도메인 라우팅을 도입한다(로드맵).

## 환경변수 (dev 기준)

- **FE `NEXT_PUBLIC_API_BASE_URL` = 빈 값**(미설정). 프록시를 쓰므로 `client.ts` 의 `BASE_URL ?? ""` 로 same-origin `/api/*` 를 호출한다. 별도 `.env.local` 없이 동작한다.
- BE Provider 키 미설정 → 전부 **Mock**. 유료 외부 호출·키 없이 전체 흐름 동작(§0.16).

## 실행 순서

```bash
# 1) BE (apimgr) — 포트 8000
cd apimgr
python -m venv .venv                                   # 최초 1회
.venv/Scripts/python -m pip install -e ".[dev]"        # 최초 1회
.venv/Scripts/python main.py                           # 진입점 main.run() — 포트 8000, reload 켜짐
# (동등한 명시 실행) .venv/Scripts/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 2) FE (hairsoui) — 포트 3000 (다른 터미널)
cd hairsoui
npm install                                            # 최초 1회
npm run dev
```

브라우저에서 <http://localhost:3000> 접속. FE 의 API 호출은 자동으로 `/api/*` → BE 로 프록시된다.

## 왕복 스모크 (프록시 경유, 검증됨)

```bash
# 202 + generation_id
curl -s -X POST http://127.0.0.1:3000/api/v1/video-generations \
  -H "Content-Type: application/json" \
  -d '{"consultation_id":"c-1","image_asset_id":"a-1","prompt":"jaw length bob","duration_seconds":5,"aspect_ratio":"9:16","quality":"720p","idempotency_key":"idem-1"}'

# 상태 조회 (SUBMITTED → PROCESSING → SUCCEEDED)
curl -s http://127.0.0.1:3000/api/v1/generations/<generation_id>
```

검증 결과(Mock): `POST → 202 SUBMITTED`, 폴링 `PROCESSING → SUCCEEDED`, 같은 `idempotency_key` 재요청 시 **동일 generation_id** 반환.

## 주의 (알려진 경계)

- `/health` 는 `/api` prefix 밖(`GET /health`)이라 **프록시(/api/*)로는 닿지 않는다.** 헬스체크는 BE 에 직접(`http://127.0.0.1:8000/health`). FE 는 health 를 호출하지 않으므로 문제 없음.
- 인메모리 저장소는 **단일 프로세스·재시작 시 초기화**(스캐폴드). 실 DB(Supabase) 저장소는 `DATABASE_URL` 설정 시 활성(로드맵 정합 진행 중).
- Mock 상태 전진은 데모용 `BackgroundTask` 다. 실 Worker 큐는 로드맵(§4.9).
