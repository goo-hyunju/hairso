# 산출물 상태 라벨 (완료기준 앵커 · P0)

산출물을 **정직하게** 구간별로 라벨링한다(구현·검증완료 / opt-in 실구현 / Mock / 미구현-로드맵). "빌드 통과 = 완성"으로 오해 금지 — 실질은 검증·정합.

## `[구현·검증완료]` — 실제 빌드·테스트 통과
### BE (apimgr)
- 도메인: enums(GenerationStatus 10 / ErrorCode 18 / ProviderName 7 / ProviderJobStatus 4 / CreditTxType), 타입별 상태 전이표(IMAGE엔 POST_PROCESSING 없음), ProviderJobStatus→내부 매핑, 도메인 dataclass 모델.
- Mock Provider 4종(image_analysis/image_generation/video_generation/studio_draft) — video 8시나리오. **opt-in 실구현:** SELF_HOSTED_WAN(ml `/video/i2v` job 등록→폴링→`/output` MP4 저장, 폴링 한도 초과 시 FAILED) · LOCAL_SD(ml `/restyle`) · OLLAMA(초안, 실패 시 Mock fallback). PixVerse 는 `NotImplementedError` 스텁, FAL_WAN/WAN_CLOUD_API/GEMINI 는 enum 만 존재.
- in-memory Repository(전체 객체 영속 `update`) + idempotency 근사, GenerationService(제출·상태반영 no-op·fail/complete 일원화), Worker(POST_PROCESSING→SUCCEEDED 상태 전이 완료 경로 — 실 FFmpeg/R2 후처리는 로드맵), WebhookService(서명검증[ts+payload 결합]·(provider,event_id) 중복 무시·후처리 멱등). 조회발 lazy advance(`GET /generations/{id}`·`GET /studio/projects/{id}` 가 비터미널 VIDEO 작업을 1회 전진 — `DATABASE_URL` 로 메타가 영속된 경우의 BE 재시작 복구용, Mock 제외; `tests/test_lazy_advance.py` 는 함수 단위 테스트).
  - ⚠️ **중복 무시·후처리 등록은 인메모리 set(스캐폴드)** — 프로세스 재시작·멀티워커·다중 인스턴스에서는 깨진다. 운영 수준 중복 방지는 DB 영속(처리 event UNIQUE)이 담당한다([Mock]/[미구현-로드맵]). 서명 포맷도 스캐폴드 제네릭 HMAC(ts+payload 결합, 실 Provider 규격은 unverified). **로드맵:** 실 webhook 은 event_id·external_job_id·status 등 이벤트 필드를 헤더/쿼리가 아닌 **서명된 payload 본문에서 파생**해야 위조를 막는다(현재 스텁은 헤더/쿼리 인자).
- FastAPI 라우터 7개 모듈·15 라우트(health / consultations[스텁] / style[Mock 고정] / assets×2 / video-generations·image-generations·generations 상태 / studio×6(download 포함) / webhooks[스텁]), 202 비동기 — 실 Worker 큐 없이 데모용 BackgroundTasks 폴링.
- 검증(2026-10-17 실행): `compileall` OK · `pytest` **107 passed · 5 skipped**(Supabase 라운드트립은 `DATABASE_URL` 미설정 시 skip) · TestClient 스모크(health/analyze/202/status/idempotent/404/assets/studio/webhook).
### FE (hairsoui)
- Next 15 App Router·TS strict·Tailwind v4·Zod, 반응형 layout/landing(viewport).
- 계약 타입/Zod(`schemas.ts`), API 클라이언트(오류 envelope 파싱), generations 함수.
- 상태 Mapper(10키), 오류코드→메시지(18키), 클라 이미지 검증 순수함수, Button/AspectRatioMedia, Studio 단계형 flow.
- 검증(2026-10-17 실행): `typecheck` 0 · `test` **20 passed** · `lint` 0 · `build` 통과(`/`, `/studio`, `/try` 정적).
### 계약 (F8 정합 — 정직한 강제 범위)
- **테스트로 강제되는 축:** ①**Enum 값·순서** — `contract/enums.json`(BE 정본 + FE 사본) ↔ BE `domain/enums.py` ↔ FE Zod `schemas.ts`/`errors.ts` 를 양쪽 parity 테스트(BE `test_contract_enums.py` `assertEqual`, FE `contract.test.ts` `deepEqual`)가 순서까지 대조. ②**필드명(snake_case)** — 와이어 키를 snake 단일화(구조적 보장).
- **테스트로 강제되지 않는 축:** ③**날짜 형식** ④**Nullable·타입** — live 응답에 TZ-aware 날짜 필드가 **존재한다**(`ConsultationResponse.created_at`, `apimgr/app/api/v1/consultations.py` 에서 `datetime.now(timezone.utc)` → ISO8601+offset 직렬화, §5.2 런타임 충족). 단 이 축은 parity 테스트로 **강제되지 않으며**, FE 에 consultation 응답 Zod 스키마도 아직 없다(상담 FE 는 P11 로드맵). **로드맵:** 상담 FE Zod 추가 시 날짜/Nullable parity 테스트(또는 BE OpenAPI 파생)를 함께 도입해 4축 전부를 테스트로 강제. **현재 "4축 전부 테스트 강제"라고 주장하지 않는다.**

## `[Mock]` — 실 외부 없이 동작
- 모든 AI Provider 기본 Mock(§0.16). 저장소 기본 인메모리·LOCAL_DISK. opt-in 실구현(OLLAMA / LOCAL_SD / SELF_HOSTED_WAN / Supabase Storage·DB / 선택적 JWT)은 env 설정 시에만 활성. Mock 비용 `Decimal("0.00")` = PLACEHOLDER(실 요금 아님).
- 인메모리 저장소(단일 프로세스, 기본). `DATABASE_URL` 설정 시 Supabase Repository(generations/assets/studio) 로 교체되며 idempotency 는 DB UNIQUE 가 담당(0001 적용 범위). Studio 테이블(0003)은 미적용 — 설정 시 Studio 경로는 0003 적용이 선행돼야 동작.

## `[미구현-로드맵]` — 검증 불가 영역(정직하게 미구현)
- 실 외부 AI 연동: Gemini(분석·이미지 편집) · PixVerse(V6) · fal(Wan Turbo) · Wan Cloud. (키·요금·API 스펙 미검증)
- 운영용 provider queue/retry/SLA, ml job 영속화(현재 메모리·TTL 없음), 1:1 비율·1080p 해상도 매핑(현재 9:16·480p 로 강등). (Wan 2.2 TI2V-5B 로컬 추론 자체는 `ml/wan_video.py` 로 구현됨 — opt-in 실구현)
- 0003 Studio 테이블 적용·나머지 7테이블(salons…credit_transactions), Worker 큐·FFmpeg 후처리, R2(Supabase Storage 가 opt-in 으로 대체 중). Alembic 미도입(SQL 파일 수동 적용, 사용자 관리 §4.19).
- FE 카메라 실 스트림·MediaPipe·세 모드 화면·PWA·로그인 연동(토큰 공급자 훅만 존재)·Preview/QR(자리표시). (업로드 왕복·상태 폴링은 구현됨)
- 인증 필수화(현재 Supabase JWT 선택적 검증만), 크레딧 실계산·예약·환불, QR/공유, 상담 영속 저장.
  - ⚠️ **금전 정밀도 부채:** 현재 금전 와이어값은 float(표시용 추정, FE z.number() 일치). DB 원장은 numeric/Decimal 정밀. 실 과금·크레딧 API 도입 시 와이어 정밀도(string decimal / minor-unit)를 재검토해야 한다(부동소수점 손실 방지, §11 무결성). 상세: `apimgr/docs/api-contract.md`.

## 미검증·외부 사실 (unverified)
- PixVerse 0.20 USD·V6/C1·Ai-trace-id, fal 가격, Wan 사양, Gemini 기능 등은 **기획서 주장(미검증)**. 코드 하드코딩 금지·env/Registry.
- 설치 버전(fastapi 0.139.0, next 15.5.20 등)은 설치 시점 lock 실측값(향후 갱신 가능).
- **검증 로그(pytest 107 passed·5 skipped, FE test 20, typecheck/lint 0, build 통과)는 2026-10-17 로컬에서 실제 실행한 결과다.** 소스 embed 만으로는 재현 불가(빌드·테스트 실행 필요) — 라벨은 실행 로그 기준의 검증 결과다.
