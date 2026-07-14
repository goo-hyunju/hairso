# TEST_SCENARIOS

## BE (apimgr — pytest 44 + TestClient)
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
### API (test_api, TestClient)
- 404/422 가 **오류 envelope**`{error:{error_code,message,request_id}}` 형식(404→NOT_FOUND, 빈 prompt→VALIDATION_ERROR), video-generations 202+SUBMITTED, estimated_cost_usd는 **number**(float).
### 계약 (test_contract_enums)
- domain enum ↔ contract/enums.json 일치(6종).
### TestClient 스모크
- health 200 · analyze 200 · video-generations **202** · status 200 · idempotent 동일 id · 404.

## FE (hairsoui — node --test 12)
- **parity**: Zod enum(GenerationStatus 10·Provider 6·VideoProvider 5·Image 2·ErrorCode 18) ↔ contract/enums.json.
- **mapper**: generationStatusView 10키 완전성 + isTerminal.
- **validation**: MIME/크기/해상도/파이프라인 첫 실패.

## 로드맵 시나리오 (미구현)
- 카메라 권한 허용/거부/장치없음/모바일/Stream 종료/새로고침 복원(실기기, §8.1).
- 실 Provider 오류/타임아웃/콘텐츠 차단/잔액 부족, Webhook 순서역전, 결과 다운로드 실패 후처리.
- 영상 모델 품질 평가(기획서 §21): 동일 이미지 20장 × 모델별 배점.
