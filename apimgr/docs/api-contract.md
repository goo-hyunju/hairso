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
| POST | `/api/v1/assets` | 201 | ✅(FACE_SOURCE 업로드·서버 시그니처 검증) |
| GET | `/api/v1/assets/{asset_id}/content` | 200 | ✅(인증된 owner_id 일치 시 반환, 익명 에셋 다운로드 거부 — 상담/share 정책 로드맵) |
| POST | `/api/v1/video-generations` | **202** | ✅(Mock provider 기본, SELF_HOSTED_WAN 로컬 MP4 opt-in, idempotent) |
| POST | `/api/v1/image-generations` | **202** | ✅(Mock/Local image provider 스캐폴드) |
| GET | `/api/v1/generations/{id}` | 200 | ✅(image/video 공통 정본) |
| POST | `/api/v1/studio/projects` | 201 | ✅(Promotion Short project 생성, Mock/in-memory) |
| GET | `/api/v1/studio/projects/{id}` | 200 | ✅(project + draft + render 상태 조회) |
| POST | `/api/v1/studio/projects/{id}/draft` | 200 | ✅(script/storyboard 초안 생성 — MOCK 기본, OLLAMA 로컬 옵션) |
| PATCH | `/api/v1/studio/projects/{id}/draft` | 200 | ✅(편집본 저장) |
| POST | `/api/v1/studio/projects/{id}/render` | **202** | ✅(기존 generation job 재사용, idempotent) |
| POST | `/api/v1/webhooks/pixverse` | 200 | ✅(서명검증·server clock freshness·secret fail-closed·중복안전 골격) |
| POST | `/api/v1/style/recommend` | 200 | 로드맵 |
| POST | `/api/v1/results/{id}/share` | 201 | 로드맵 |
| GET | `/share/{share_token}` | 200 | 로드맵(공개) |

## 주요 스키마
### POST /api/v1/assets (요청/응답)
요청은 `multipart/form-data`이며 필드명은 `file`이다.

```json
{ "asset_id": "uuid-or-opaque", "asset_type": "FACE_SOURCE", "mime_type": "image/png", "byte_size": 12345 }
```

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

### Studio project 생성
```json
{
  "template_type": "PROMOTION_SHORT",
  "category": "HAIR",
  "title": "봄맞이 클리닉 이벤트",
  "offer_text": "첫 방문 20% 할인, 이번 달 한정",
  "cta_text": "오늘 예약 문의하기",
  "duration_seconds": 15,
  "target_audience": "신규 고객",
  "tone": "FRIENDLY",
  "asset_ids": [],
  "logo_asset_id": null,
  "disclaimer": "상세 조건은 매장 상담 후 확정됩니다."
}
```
- `duration_seconds`는 Studio 최종 산출 길이(`15 | 30`)다. 기존 `/video-generations`의 `5 | 8` provider clip 계약은 변경하지 않는다.
- 응답은 project/draft/render 상태와 `output_asset_id`만 반환한다. signed URL, storage key, provider raw payload는 반환하지 않는다.
- `storage` 응답은 비밀 없는 설정 요약(`backend`, `storage_profile_name`, `output_prefix`, `output_retention_days`)만 제공한다.
- `title`, `offer_text`, `cta_text`, `target_audience`, `disclaimer`는 URL, signed URL, storage key, Base64 형태를 포함하면 `VALIDATION_ERROR`로 거부한다.

### Studio render
```json
{ "idempotency_key": "uuid-or-safe-token" }
```
```json
{ "project_id": "uuid", "generation_id": "uuid", "status": "SUBMITTED" }
```
- 같은 project에 이미 render job이 있으면 새 job을 만들지 않고 기존 `generation_id`를 반환한다.
- Mock render와 `SELF_HOSTED_WAN` 로컬 render는 기존 `GET /api/v1/generations/{id}` 상태 조회 계약을 재사용한다.
- `DEFAULT_VIDEO_PROVIDER=SELF_HOSTED_WAN`이면 BE가 로컬 추론 서버(`LOCAL_VIDEO_INFERENCE_URL` + `LOCAL_VIDEO_ENDPOINT_PATH`)에 backend-only 요청을 보낸다. 로컬 서버 응답은 `video/mp4` 바이트여야 하며, 성공 시 `GENERATED_VIDEO` 에셋으로 저장한다.
- 이미지가 없는 Mock render는 내부 `VideoGenerationInput.image_asset_id`와 generation의 `input_asset_id`를 `null`로 둘 수 있다. `SELF_HOSTED_WAN`은 source asset이 있으면 BE 내부에서만 바이트를 읽어 전달하고, URL·signed URL·storage key·Base64는 요청/응답에 넣지 않는다.

### Studio draft provider
- 공개 응답 구조는 `StudioDraftSchema` 그대로 유지한다: `script.hook`, `script.narration`, `script.cta`, `storyboard[].caption`, `storyboard[].visual_prompt`.
- 기본값은 `DEFAULT_STUDIO_DRAFT_PROVIDER=MOCK`이다. `OLLAMA`는 BE 내부에서만 로컬 `/api/generate`를 호출하는 옵션이다.
- `OLLAMA` 실패, 모델 미설정, 비로컬 URL 설정 시 기존 Mock 초안으로 fallback한다.
- 초안 provider에는 검증된 project 텍스트와 asset 개수만 전달하고, 이미지 URL·signed URL·storage key·Base64는 전달하지 않는다.
- `PATCH /draft`의 script/storyboard 텍스트도 같은 민감 문자열 검증을 통과해야 저장된다.
- provider가 반환한 script/storyboard도 저장 전 검증하고, render 시작 직전 저장 draft를 다시 검증한다.

## 금전값 직렬화 (무결성 부채 명기)
- `estimated_cost_usd` 등 금전 **와이어값은 float(JSON number)** — FE `z.number()` 계약 일치용. **표시용 추정치에 한정**한다.
- DB 원장(`generations.*_cost_usd`, `credit_transactions.amount_credit`)은 `numeric(12,4)`, 도메인은 `Decimal` 로 **정밀** 유지한다.
- ⚠️ **부채:** float 와이어는 부동소수점 정밀도 손실이 누적될 수 있다(§11 무결성). **실 과금·크레딧 차감 API 도입 시**(로드맵) 금전 와이어 정밀도를 **string decimal 또는 minor-unit(정수 센트)** 로 재검토해야 한다. 현재는 Mock `Decimal("0.00")` placeholder 라 즉시 결함은 아니다.

## 비동기 흐름 (§5.4)
`POST /video-generations → 202 + generation_id` → Worker 가 Provider 폴링/Webhook → 상태 전이 → 완료.
FE 는 `GET /api/v1/generations/{id}` 로 상태 조회(Polling). 상태 10종은 `contract/enums.json`.

## 보안 주의
- `/api/v1/assets/{asset_id}/content`는 현재 인증된 `owner_id` 일치만 허용한다. 실 고객 얼굴 원본에 쓰기 전 상담 단위 권한, 공유 토큰, 만료, 동의 정책까지 확장해야 한다.
- Webhook 스캐폴드는 실 Provider payload 규격을 아직 파싱하지 않는다. 실 연동 전 payload schema 검증과 처리 event 영속화가 필요하다.
