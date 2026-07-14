# apimgr — API 계약

> **정본 = FastAPI 자동 생성 OpenAPI** (`/docs`, `/openapi.json`). 이 문서는 요약이며, 다르면 OpenAPI 가 우선.
> FE(`hairsoui`)의 Zod 스키마는 이 계약에 정렬한다. 와이어 키는 snake_case.

## 공통
- prefix: `/api/v1` (전 엔드포인트). 공개 결과 `GET /share/{share_token}` 만 `/api` 밖.
- 인증: 자체 JWT(로드맵). 오류 envelope: `{ "error": { "error_code", "message", "request_id" } }`.
- 오류코드(18): `contract/enums.json` ErrorCode 참조.

## 엔드포인트 (스캐폴드 구현 상태 표기)
| Method | Path | 상태코드 | 구현 |
|---|---|---|---|
| GET | `/health` | 200 | ✅ |
| POST | `/api/v1/consultations` | 201 | ✅(스텁 — 저장 로드맵) |
| POST | `/api/v1/style/analyze` | 200 | ✅(Mock 분석) |
| POST | `/api/v1/video-generations` | **202** | ✅(Mock provider, idempotent) |
| GET | `/api/v1/generations/{id}` | 200 | ✅(image/video 공통 정본) |
| POST | `/api/v1/webhooks/pixverse` | 200 | ✅(서명검증·중복안전 골격) |
| POST | `/api/v1/assets/upload` | 201 | 로드맵 |
| POST | `/api/v1/style/recommend` | 200 | 로드맵 |
| POST | `/api/v1/style/image-generate` | 202 | 로드맵 |
| POST | `/api/v1/results/{id}/share` | 201 | 로드맵 |
| GET | `/share/{share_token}` | 200 | 로드맵(공개) |

## 주요 스키마
### POST /api/v1/video-generations (요청)
```json
{ "consultation_id": "...", "image_asset_id": "...", "prompt": "...",
  "negative_prompt": null, "duration_seconds": 5, "aspect_ratio": "9:16",
  "quality": "720p", "seed": null, "idempotency_key": "..." }
```
- `image_asset_id`(UUID) — imageUrl 아님(§4.6). `duration_seconds` ∈ {5,8}. `idempotency_key` 필수(중복 방지).

### 202 응답 / GET status 응답
```json
{ "generation_id": "uuid", "status": "SUBMITTED" }
```
```json
{ "generation_id": "uuid", "generation_type": "VIDEO", "status": "PROCESSING",
  "provider": "MOCK", "estimated_cost_usd": 0.0, "output_asset_id": null, "error_code": null }
```

## 금전값 직렬화 (무결성 부채 명기)
- `estimated_cost_usd` 등 금전 **와이어값은 float(JSON number)** — FE `z.number()` 계약 일치용. **표시용 추정치에 한정**한다.
- DB 원장(`generations.*_cost_usd`, `credit_transactions.amount_credit`)은 `numeric(12,4)`, 도메인은 `Decimal` 로 **정밀** 유지한다.
- ⚠️ **부채:** float 와이어는 부동소수점 정밀도 손실이 누적될 수 있다(§11 무결성). **실 과금·크레딧 차감 API 도입 시**(로드맵) 금전 와이어 정밀도를 **string decimal 또는 minor-unit(정수 센트)** 로 재검토해야 한다. 현재는 Mock `Decimal("0.00")` placeholder 라 즉시 결함은 아니다.

## 비동기 흐름 (§5.4)
`POST /video-generations → 202 + generation_id` → Worker 가 Provider 폴링/Webhook → 상태 전이 → 완료.
FE 는 `GET /api/v1/generations/{id}` 로 상태 조회(Polling). 상태 10종은 `contract/enums.json`.
