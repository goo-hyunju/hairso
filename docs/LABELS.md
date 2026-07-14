# 산출물 3구간 라벨 (완료기준 앵커 · P0)

이번 `/tr` 산출을 **정직하게** 3구간으로 라벨링한다. "빌드 통과 = 완성"으로 오해 금지 — 실질은 검증·정합.

## `[구현·검증완료]` — 실제 빌드·테스트 통과
### BE (apimgr)
- 도메인: enums(GenerationStatus 10 / ErrorCode 18 / ProviderName 6 / ProviderJobStatus 4 / CreditTxType), 타입별 상태 전이표(IMAGE엔 POST_PROCESSING 없음), ProviderJobStatus→내부 매핑, 도메인 dataclass 모델.
- Mock Provider 3종(image_analysis/image_generation/video_generation) — 8시나리오.
- in-memory Repository(전체 객체 영속 `update`) + idempotency 근사, GenerationService(제출·상태반영 no-op·fail/complete 일원화), Worker(POST_PROCESSING→SUCCEEDED 상태 전이 완료 경로 — 실 FFmpeg/R2 후처리는 로드맵), WebhookService(서명검증[ts+payload 결합]·(provider,event_id) 중복 무시·후처리 멱등).
  - ⚠️ **중복 무시·후처리 등록은 인메모리 set(스캐폴드)** — 프로세스 재시작·멀티워커·다중 인스턴스에서는 깨진다. 운영 수준 중복 방지는 DB 영속(처리 event UNIQUE)이 담당한다([Mock]/[미구현-로드맵]). 서명 포맷도 스캐폴드 제네릭 HMAC(ts+payload 결합, 실 Provider 규격은 unverified). **로드맵:** 실 webhook 은 event_id·external_job_id·status 등 이벤트 필드를 헤더/쿼리가 아닌 **서명된 payload 본문에서 파생**해야 위조를 막는다(현재 스텁은 헤더/쿼리 인자).
- FastAPI 라우터 6(health/consultations/style/video-generations/generations/webhooks), 202 비동기.
- 검증: `compileall` OK · `pytest` **44 passed** · TestClient 스모크(health/analyze/202/status/idempotent/404).
### FE (hairsoui)
- Next 15 App Router·TS strict·Tailwind v4·Zod, 반응형 layout/landing(viewport).
- 계약 타입/Zod(`schemas.ts`), API 클라이언트(오류 envelope 파싱), generations 함수.
- 상태 Mapper(10키), 오류코드→메시지(18키), 클라 이미지 검증 순수함수, Button/AspectRatioMedia.
- 검증: `typecheck` 0 · `test` **12 passed** · `build` 0 · `lint` 0.
### 계약 (F8 정합 — 정직한 강제 범위)
- **테스트로 강제되는 축:** ①**Enum 값·순서** — `contract/enums.json`(BE 정본 + FE 사본) ↔ BE `domain/enums.py` ↔ FE Zod `schemas.ts`/`errors.ts` 를 양쪽 parity 테스트(BE `test_contract_enums.py` `assertEqual`, FE `contract.test.ts` `deepEqual`)가 순서까지 대조. ②**필드명(snake_case)** — 와이어 키를 snake 단일화(구조적 보장).
- **테스트로 강제되지 않는 축:** ③**날짜 형식** ④**Nullable·타입** — live 응답에 TZ-aware 날짜 필드가 **존재한다**(`ConsultationResponse.created_at`, `apimgr/app/api/v1/consultations.py` 에서 `datetime.now(timezone.utc)` → ISO8601+offset 직렬화, §5.2 런타임 충족). 단 이 축은 parity 테스트로 **강제되지 않으며**, FE 에 consultation 응답 Zod 스키마도 아직 없다(상담 FE 는 P11 로드맵). **로드맵:** 상담 FE Zod 추가 시 날짜/Nullable parity 테스트(또는 BE OpenAPI 파생)를 함께 도입해 4축 전부를 테스트로 강제. **현재 "4축 전부 테스트 강제"라고 주장하지 않는다.**

## `[Mock]` — 실 외부 없이 동작
- 모든 AI Provider 기본 Mock(§0.16). Mock 비용 `Decimal("0.00")` = PLACEHOLDER(실 요금 아님).
- 인메모리 저장소(단일 프로세스). idempotency setdefault 근사(실서비스는 DB UNIQUE).

## `[미구현-로드맵]` — 검증 불가 영역(정직하게 미구현)
- 실 외부 AI 연동: Gemini(분석·이미지 편집) · PixVerse(V6) · fal(Wan Turbo) · Wan Cloud. (키·요금·API 스펙 미검증)
- 실 DB(PostgreSQL·Repository), 마이그레이션(Alembic — 사용자 관리 §4.19), R2 스토리지, Worker 큐·FFmpeg 후처리.
- FE 카메라 실 스트림·MediaPipe·업로드 왕복·Polling 실동작·세 모드 화면·PWA.
- 인증(JWT) 실구현, 크레딧 실계산·예약·환불, QR/공유.
  - ⚠️ **금전 정밀도 부채:** 현재 금전 와이어값은 float(표시용 추정, FE z.number() 일치). DB 원장은 numeric/Decimal 정밀. 실 과금·크레딧 API 도입 시 와이어 정밀도(string decimal / minor-unit)를 재검토해야 한다(부동소수점 손실 방지, §11 무결성). 상세: `apimgr/docs/api-contract.md`.

## 미검증·외부 사실 (unverified)
- PixVerse 0.20 USD·V6/C1·Ai-trace-id, fal 가격, Wan 사양, Gemini 기능 등은 **기획서 주장(미검증)**. 코드 하드코딩 금지·env/Registry.
- 설치 버전(fastapi 0.139.0, next 15.5.20 등)은 설치 시점 lock 실측값(향후 갱신 가능).
- **검증 로그(pytest 44·test 12·typecheck/build/lint 0)는 main 이 로컬에서 실제 실행한 결과다.** 소스 embed 만으로는 재현 불가(빌드·테스트 실행 필요) — 라벨은 실행 로그 기준의 검증 결과다.
