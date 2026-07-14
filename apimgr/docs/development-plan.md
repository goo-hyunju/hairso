# apimgr — 개발 계획 (로드맵)

기획서 §19 주차 계획을 BE 관점으로 매핑. **이번 스캐폴드가 완료한 범위와 남은 로드맵**을 3구간 라벨로 구분한다.

## 이번 스캐폴드 `[구현·검증완료]`
- 계층 골격(api/core/domain/schemas/services/providers/repositories/workers).
- 도메인: GenerationStatus(10)·ErrorCode(18)·ProviderName(6)·CreditTxType enum, 타입별 상태 전이표, ProviderJobStatus 매핑.
- Mock Provider 3종(image_analysis / image_generation / video_generation) — 8시나리오.
- in-memory Repository + idempotency 근사, GenerationService, WebhookService(서명검증·중복안전).
- FastAPI 라우터(health/consultations/style/video-generations/generations/webhooks), 202 비동기.
- 참고 DDL(`db/schema.sql`), `contract/enums.json`, pytest 44 + TestClient 스모크.

## 로드맵 `[미구현-로드맵]`
- **2주차:** Gemini 실 분석 연동(스타일 JSON), 사진 품질 서버 재검증(§4.14).
- **3주차:** Gemini 이미지 편집 실 연동, 이미지 3종 배치 생성, 결과 asset 저장.
- **4주차:** PixVerse/fal 실 API, Provider Registry 실 선택, Worker 큐(초기 PostgreSQL Job), Webhook 실 payload 파싱, 재시도 지수백오프, R2 다운로드·저장.
- **5주차:** 상담 실 저장(Repository→PostgreSQL), 크레딧 계산·예약·확정·환불, QR/공유 토큰.
- **6주차:** 관리자 비용 대시보드, 만료 파일 삭제 Worker, 감사 로그, 배포.

## DB
- 실제 스키마 적용/마이그레이션(Alembic)은 **사용자 관리**(§4.19). `db/schema.sql` 은 설계 참고본. Alembic 도입은 스키마 확정 후.

## 확인 필요 (사용자)
- 실 외부 API 키(Gemini/PixVerse/fal/Wan), Supabase·R2 자격, BE 실행 포트·CORS 대상 오리진.
