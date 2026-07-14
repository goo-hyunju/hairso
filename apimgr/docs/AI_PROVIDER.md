# apimgr — AI Provider

> ⚠️ 이 문서의 외부 수치(가격·모델명·기능)는 **기획서 주장(미검증, unverified)** 이다. 실 요금표·API 스펙 확인 전엔 확정값이 아니며 코드에 하드코딩하지 않는다(§0.9/§4.8). 모델명은 env/Registry.

## Provider Registry (단일 명칭표)
`PIXVERSE / FAL_WAN / WAN_CLOUD_API / SELF_HOSTED_WAN / GEMINI / MOCK`
- 규칙 §4.8: `WAN_CLOUD_API` 채택. 기획서 §12 `ALIBABA_WAN` 은 별칭(각주).
- GEMINI = image_analysis/image_generation 소속(영상 provider 아님 → VideoProviderName 5종에서 제외).

## 계층
- 공통 인터페이스: `providers/{image_analysis,image_generation,video_generation}/base.py`.
- Provider 상태 = `ProviderJobStatus`(PENDING/PROCESSING/SUCCEEDED/FAILED, 4값). Service 가 내부 `GenerationStatus`(10값)로 매핑(`status_mapping.py`).
  - VIDEO: provider SUCCEEDED → 내부 POST_PROCESSING(후처리 대기) → Worker 완료 시 SUCCEEDED.
  - IMAGE: 후처리 없음 → provider SUCCEEDED → 내부 SUCCEEDED 직행.

## 공통 입력/결과 (Provider 전용 필드 의존 금지)
- `VideoGenerationInput`: image_asset_id, prompt, duration_seconds, aspect_ratio, quality, idempotency_key, negative_prompt?, seed?.
- `VideoSubmissionResult`: provider, external_job_id, ai_trace_id?(PixVerse), estimated_cost_usd?(Decimal).

## Mock (`[Mock]` — 기본, §0.16)
8시나리오: SUCCESS/SLOW/SUBMIT_FAIL/RATE_LIMIT/NO_BALANCE/POLICY_BLOCK/ASYNC_FAIL/DOWNLOAD_FAIL. 비용 `Decimal("0.00")` PLACEHOLDER.

## 로드맵 `[미구현-로드맵]`
- PixVerse Platform API(이미지 업로드→img_id→i2v→video_id→webhook/폴링→다운로드). `Ai-trace-id`·`img_id`·`video_id`·모델 `V6/C1` 은 unverified 외부 스펙.
- fal Wan2.2 Turbo(저비용 대체), Wan Cloud API(프리미엄), Gemini(분석·이미지 편집).
- 실 Webhook 서명검증(PixVerse Secret), 재시도 지수백오프, 장애 시 자동 대체 Provider.
