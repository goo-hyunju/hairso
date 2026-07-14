# hairsoui — API 계약 (FE 관점)

> **정본 = apimgr FastAPI OpenAPI**(`/openapi.json`). FE Zod 스키마(`lib/api/schemas.ts`)는 이 계약에 정렬(파생).
> 이 문서는 FE 소비 관점 요약. enum 정본 사본은 `contract/enums.json`(parity 테스트가 대조).

## 클라이언트
- Base URL: `process.env.NEXT_PUBLIC_API_BASE_URL`(분리 저장소 — 값 **미확정**, BE 포트/CORS 확정 후 주입).
- 와이어 키 snake_case. 오류 envelope `{ error: { error_code, message, request_id } }` → `ApiError(code, status, requestId)` 로 변환.
- 모든 응답은 `schema.parse()` 검증(타입 단언 금지).

## 사용 함수 (`lib/api/generations.ts`)
- `createVideoGeneration(body)` → `POST /api/v1/video-generations` → `{ generation_id, status }`(202).
- `getGenerationStatus(id)` → `GET /api/v1/generations/{id}` → `{ generation_id, generation_type, status, provider, estimated_cost_usd, output_asset_id, error_code }`.

## enum (contract/enums.json 정본)
- `GenerationStatus`(10) — 상태 Mapper 10키와 일치.
- `ProviderName`(6) / `VideoProviderName`(5, GEMINI 제외) / `ImageProviderName`(GEMINI,MOCK).
- `ApiErrorCode`(18) — 오류 메시지 Mapper 와 일치.

## 미확정 (BE 협의)
- base URL·포트·CORS 오리진. Idempotency key 생성 규칙(FE UUID vs 서버). 로드맵 엔드포인트(assets/recommend/image-generate/share) 스키마.
