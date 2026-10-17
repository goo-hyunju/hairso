# apimgr — AI Provider

> ⚠️ 이 문서의 외부 수치(가격·모델명·기능)는 **기획서 주장(미검증, unverified)** 이다. 실 요금표·API 스펙 확인 전엔 확정값이 아니며 코드에 하드코딩하지 않는다(§0.9/§4.8). 모델명은 env/Registry.

## Provider Registry (단일 명칭표)
`MOCK / GEMINI / PIXVERSE / FAL_WAN / WAN_CLOUD_API / SELF_HOSTED_WAN / LOCAL_SD`
- 규칙 §4.8: `WAN_CLOUD_API` 채택. 기획서 §12 `ALIBABA_WAN` 은 별칭(각주).
- GEMINI = image_analysis/image_generation 소속(영상 provider 아님 → VideoProviderName 5종에서 제외).
- OLLAMA = Studio draft 전용 로컬 텍스트 provider 옵션. generation 비용·상태 provider enum 에 넣지 않는다.

## 계층
- 공통 인터페이스: `providers/{image_analysis,image_generation,video_generation,studio_draft}/base.py`.
- Provider 상태 = `ProviderJobStatus`(PENDING/PROCESSING/SUCCEEDED/FAILED, 4값). Service 가 내부 `GenerationStatus`(10값)로 매핑(`status_mapping.py`).
  - VIDEO: provider SUCCEEDED → 내부 POST_PROCESSING(후처리 대기) → Worker 완료 시 SUCCEEDED.
  - IMAGE: 후처리 없음 → provider SUCCEEDED → 내부 SUCCEEDED 직행.

## 공통 입력/결과 (Provider 전용 필드 의존 금지)
- `VideoGenerationInput`: image_asset_id(UUID 또는 Studio mock text-only 내부 경로의 null), prompt, duration_seconds, aspect_ratio, quality, idempotency_key, negative_prompt?, seed?, backend-only source_image?.
- `VideoSubmissionResult`: provider, external_job_id, ai_trace_id?(PixVerse), estimated_cost_usd?(Decimal).
- `VideoStatusResult`: provider status, output_url?(mock/remote 내부 참조), output_bytes?(backend-only MP4 바이트), error_code?.

## Mock (`[Mock]` — 기본, §0.16)
8시나리오: SUCCESS/SLOW/SUBMIT_FAIL/RATE_LIMIT/NO_BALANCE/POLICY_BLOCK/ASYNC_FAIL/DOWNLOAD_FAIL. 비용 `Decimal("0.00")` PLACEHOLDER.

## Self-hosted Wan (`[구현]` — backend-only opt-in)
- 활성화: `DEFAULT_VIDEO_PROVIDER=SELF_HOSTED_WAN`.
- 설정: `LOCAL_VIDEO_INFERENCE_URL`, `LOCAL_VIDEO_ENDPOINT_PATH=/video/i2v`, `LOCAL_VIDEO_TIMEOUT_SECONDS`, `SELF_HOSTED_WAN_VIDEO_MODEL`.
- BE가 로컬 호스트 또는 compose 내부 `ml` 서비스만 호출한다. 외부 URL은 거부한다.
- 고객 이미지가 필요하면 `asset_id`로 서버 내부 바이트를 읽어 multipart 파일로만 전달한다. asset URL, signed URL, storage key, Base64는 전달하지 않는다.
- 결과 MP4 는 `GET /video/i2v/{job_id}/output` 에서 받는다(POST 가 동기 `video/mp4` 를 돌려주는 응답은 하위호환). Worker는 MP4 컨테이너 서명을 확인한 뒤 `AssetService.register_generated_video()`로 저장한다.
- `ml/serve.py`의 `/video/i2v` 는 job 방식(202 + job_id → `GET /video/i2v/{job_id}` → `GET …/output`)이다. 기본은 프로세스 내 Wan 2.2 TI2V-5B Diffusers(`ml/wan_video.py`, 최초 로드 시 Hugging Face 자동 다운로드)이고, `LOCAL_VIDEO_RENDER_COMMAND` 는 외부 렌더 명령을 감싸는 대체 경로다. GPU 환경 준비는 사용자 몫이다.

## Studio Draft (`[구현]` — backend-only)
- 기본: `DEFAULT_STUDIO_DRAFT_PROVIDER=MOCK`.
- 로컬 Ollama 옵션: `DEFAULT_STUDIO_DRAFT_PROVIDER=OLLAMA`, `OLLAMA_BASE_URL`, `OLLAMA_STUDIO_DRAFT_MODEL`.
- Ollama 실패·모델 미설정·비로컬 URL 설정 시 Mock draft로 fallback.
- 검증된 project 텍스트와 asset 개수만 전달하고, 이미지 URL·signed URL·storage key·Base64는 전달하지 않는다.
- project/draft/provider-output 텍스트에 민감 media 참조 형태가 있으면 `VALIDATION_ERROR` 또는 Mock fallback으로 처리한다.
- render 시작 직전 저장 draft도 다시 검증해 legacy 데이터가 provider prompt로 나가지 않게 한다.

## 로드맵 `[미구현-로드맵]`
- PixVerse Platform API(이미지 업로드→img_id→i2v→video_id→webhook/폴링→다운로드). `Ai-trace-id`·`img_id`·`video_id`·모델 `V6/C1` 은 unverified 외부 스펙.
- fal Wan2.2 Turbo(저비용 대체), Wan Cloud API(프리미엄), Gemini(분석·이미지 편집).
- 운영 전환용 DB 원자 idempotency, 실 webhook payload 파싱/영속 dedup, provider output downloader/retry 정책.
- 실 Webhook 서명검증(PixVerse Secret), 재시도 지수백오프, 장애 시 자동 대체 Provider.
