# hairsoui — API 계약 (FE 관점)

> **정본 = apimgr FastAPI OpenAPI**(`/openapi.json`). FE Zod 스키마(`lib/api/schemas.ts`)는 이 계약에 정렬(파생).
> 이 문서는 FE 소비 관점 요약. enum 정본 사본은 `contract/enums.json`(parity 테스트가 대조).

## 클라이언트
- Dev Base URL: 기본값은 빈 문자열이다. Next 프록시가 `/api/*`를 BE `http://127.0.0.1:8000/api/*`로 전달하므로 CORS 없이 same-origin으로 호출한다.
- 운영 Base URL: 게이트웨이/도메인 구성이 확정되면 `process.env.NEXT_PUBLIC_API_BASE_URL`로 주입한다.
- 와이어 키 snake_case. 오류 envelope `{ error: { error_code, message, request_id } }` → `ApiError(code, status, requestId)` 로 변환.
- 모든 응답은 `schema.parse()` 검증(타입 단언 금지).

## 사용 함수 (`lib/api/generations.ts`)
- `createVideoGeneration(body)` → `POST /api/v1/video-generations` → `{ generation_id, status }`(202).
- `getGenerationStatus(id)` → `GET /api/v1/generations/{id}` → `{ generation_id, generation_type, status, provider, estimated_cost_usd, output_asset_id, error_code }`.
- `uploadAsset(file)` → `POST /api/v1/assets`(multipart `file`) → `{ asset_id, asset_type, mime_type, byte_size }`(201).

## Studio 함수 (`lib/api/studio.ts`)
- `createStudioProject(body)` → `POST /api/v1/studio/projects` → project 응답(201).
- `createStudioDraft(projectId)` → `POST /api/v1/studio/projects/{id}/draft` → 결정적 script/storyboard 초안.
- `updateStudioDraft(projectId, body)` → `PATCH /api/v1/studio/projects/{id}/draft` → 편집본 저장.
- `renderStudioProject(projectId, idempotencyKey)` → `POST /api/v1/studio/projects/{id}/render` → `{ project_id, generation_id, status }`(202).
- `getStudioProject(projectId)` → `GET /api/v1/studio/projects/{id}` → project + render 상태 조회.

Studio `duration_seconds`는 최종 쇼츠 길이(`15 | 30`)이고, 기존 `createVideoGeneration`의 `5 | 8`은 provider scene clip 계약으로 유지한다.

## enum (contract/enums.json 정본)
- `GenerationStatus`(10) — 상태 Mapper 10키와 일치.
- `ProviderName`(7) / `VideoProviderName`(5, GEMINI·LOCAL_SD 제외) / `ImageProviderName`(GEMINI,MOCK,LOCAL_SD).
- `ApiErrorCode`(18) — 오류 메시지 Mapper 와 일치.
- `StudioTemplateType` / `StudioCategory` / `StudioTone` / `StudioProjectStatus` — `/studio` 화면과 BE Studio API 응답 검증.

## 미확정 (BE 협의)
- 운영 게이트웨이/CORS 오리진.
- Idempotency key 생성 규칙(FE UUID vs 서버).
- 로드맵 엔드포인트(style recommend/share) 스키마.
- 실 인증/소유권 적용 뒤 `GET /api/v1/assets/{asset_id}/content` 공개 여부.
