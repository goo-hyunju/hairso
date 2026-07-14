# SECURITY

## 자격증명
- env / 승인된 secret 관리로만 주입: DATABASE_URL, STORAGE_*, GEMINI_API_KEY, PIXVERSE_API_KEY, PIXVERSE_WEBHOOK_SECRET, FAL_KEY, WAN_API_KEY, JWT_SECRET.
- 코드·Fixture·문서·테스트에 실값 금지. `apimgr/.env.example` 는 placeholder 만. `cfg/` 는 gitignore.

## 인증·권한
- 자체 JWT(salon_members.password_hash). 미용실·직원·고객 접근 제어. 401/403 = UNAUTHORIZED/FORBIDDEN.

## 파일 검증 (이중, §4.14)
- FE 1차(UX): MIME·크기·해상도·decode. BE 재검증(보안): 실제 시그니처·소유자·Asset Type·악성 여부. 확장자만 신뢰 금지.

## Webhook (§4.15)
- 타임스탬프 허용범위 → 서명 검증(HMAC 상수시간 비교) → 이벤트 스키마 → job 조회 → 중복 확인(processed_event_ids) → 상태 전이 검증 → 반영. 검증 실패 시 상태 변경 안 함. 무거운 다운로드/FFmpeg 는 Worker 로.

## Idempotency (§4.10)
- generations/credit_transactions `idempotency_key` UNIQUE. 코드 선조회만으로 중복 방지 판단 금지 — DB 제약/락 필요.

## 외부 전송 주의 (Codex ROUND)
- ROUND payload 에 `cfg/*` 등 자격증명 경로 제외. 그린필드라 실 자격증명 미생성으로 위험 최소화.

## 오류 노출
- 사용자에게 Stack Trace·Provider 원문·SQL·Storage Key·Internal ID·API Key 노출 금지. 내부 오류코드만.
