# TEST_SCENARIOS

## BE (apimgr — pytest 84 + unittest 89 + TestClient)
### 상태머신 (test_state_machine)
- VIDEO 전방 체인 CREATED→SUBMITTED→QUEUED→PROCESSING→POST_PROCESSING→SUCCEEDED→EXPIRED.
- IMAGE 는 POST_PROCESSING 없음(PROCESSING→SUCCEEDED 직행).
- SUCCEEDED 는 늦은 PROCESSING 으로 되돌지 않음. 터미널 상태 outgoing 0. 동일상태 전이 불가(no-op).
- **provider 가 중간상태(PROCESSING) 건너뛰어도 정체 안 함**: SUBMITTED/QUEUED→POST_PROCESSING(VIDEO)·→SUCCEEDED(IMAGE) 전방 스킵 허용.
### 매핑 (test_status_mapping)
- VIDEO provider SUCCEEDED → 내부 POST_PROCESSING. IMAGE → SUCCEEDED. PENDING → QUEUED. 전 값 매핑 존재.
### Mock Provider (test_mock_video_provider, 8시나리오)
- SUCCESS/SLOW(폴링)/SUBMIT_FAIL/RATE_LIMIT/NO_BALANCE/POLICY_BLOCK/ASYNC_FAIL/DOWNLOAD_FAIL.
### Service (test_generation_service)
- 제출 성공→SUBMITTED, 실패→FAILED, **idempotent 재요청 동일 id**, 늦은 이벤트 no-op.
### Webhook (test_webhook_service)
- 잘못된 서명 거부, 오래된 타임스탬프 거부, 유효 이벤트 상태 전진, **중복 event_id 멱등**, **순서역전(작업 저장 전 도착) 시 event_id 미기록·재전송 허용**.
### Worker (test_generation_worker)
- ASYNC_FAIL 시 **error_code 보존**(FAILED+GENERATION_FAILED), DOWNLOAD_FAIL 시 **FAILED(DOWNLOAD_FAILED)+repo 영속**, **POST_PROCESSING 후 성공→SUCCEEDED+output_asset 완료**, **결과 URL 부재(None)→FAILED(DOWNLOAD_FAILED)**, 터미널(SUCCEEDED)에서 fail_generation no-op(역행 방지).
- provider가 `output_bytes`로 반환한 MP4 바이트는 `GENERATED_VIDEO` asset으로 저장. mock이 아닌 URL-only 결과는 다운로드 실패로 처리.
### Self-hosted Wan Provider (test_self_hosted_wan_provider)
- `SELF_HOSTED_WAN` provider는 로컬 URL만 허용하고, 외부 URL은 거부.
- 로컬 `/video/i2v` 호출 payload에 `image_asset_id`, storage key, URL을 넣지 않고 backend-only 이미지 바이트만 multipart로 전달.
- `video/mp4` 컨테이너가 아닌 응답은 `GENERATION_FAILED`로 거부.
### API (test_api, TestClient)
- 404/422 가 **오류 envelope**`{error:{error_code,message,request_id}}` 형식(404→NOT_FOUND, 빈 prompt→VALIDATION_ERROR), video-generations 202+SUBMITTED, estimated_cost_usd는 **number**(float).
- idempotency key 경로 문자 거부, 익명 asset content 다운로드 403, webhook secret 미설정 fail-closed, stale webhook timestamp 거부.
- video/image idempotent 재요청 시 background task 중복 등록 방지.
### Studio API (test_studio_api)
- project→draft→patch→render→project status 조회 mock 흐름.
- draft 없는 render는 VALIDATION_ERROR.
- `SALON_EVENT_PROMOTION` 30초 draft는 5 scenes, 총 30초로 생성.
- URL 형태 `asset_id`는 422 VALIDATION_ERROR, 존재하지 않는 asset 참조는 400 ASSET_NOT_FOUND.
- project 텍스트의 URL형 민감 참조와 draft visual_prompt의 Base64형 media payload는 VALIDATION_ERROR.
### Studio Draft Provider (test_studio_draft_provider)
- Mock provider 30초 draft는 5/6/6/8/5초 장면으로 생성.
- Ollama provider는 네트워크 mock으로 구조화 JSON을 파싱하고 media payload key를 보내지 않음.
- 비로컬 Ollama URL과 민감 입력 텍스트는 거부.
- provider 실패 또는 민감 provider 출력 시 StudioService가 Mock draft로 fallback.
- 소유자 없는 `GENERATED_IMAGE` Studio 참조는 거부.
- legacy 민감 project/draft는 draft/render 직전 재검증에서 거부.
- asset 없는 Mock render는 provider 입력과 내부 generation의 `input_asset_id`를 null로 저장.
### 계약 (test_contract_enums)
- domain enum ↔ contract/enums.json 일치(6종).
### TestClient 스모크
- health 200 · analyze 200 · video-generations **202** · status 200 · idempotent 동일 id · 404 · Studio smoke.

## FE (hairsoui — node --test 20)
- **parity**: Zod enum(GenerationStatus 10·Provider 7·VideoProvider 5·Image 3·ErrorCode 18) ↔ contract/enums.json.
- **mapper**: generationStatusView 10키 완전성 + isTerminal.
- **validation**: MIME/크기/해상도/파이프라인 첫 실패.
- **asset schema**: 업로드 응답 검증 + 음수 byte_size 거부.

## 로드맵 시나리오 (미구현)
- 카메라 권한 허용/거부/장치없음/모바일/Stream 종료/새로고침 복원(실기기, §8.1).
- 실 Provider 오류/타임아웃/콘텐츠 차단/잔액 부족, Webhook 순서역전, 결과 다운로드 실패 후처리.
- 영상 모델 품질 평가(기획서 §21): 동일 이미지 20장 × 모델별 배점.
