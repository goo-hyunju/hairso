# TASKS — 다음 단계 작업 목록

## 이번 산출(완료)
- [x] FE+BE 스캐폴드(빌드·테스트 통과), 문서군, 도메인/스키마 설계, Mock Provider, 계약 parity.

## 사용자 확인 필요 (블로킹)
- [ ] **Codex ROUND 상한**: 사용자 지시 "10라운드" vs 규칙(codex-round.md) "최대 3회". 이번은 3회 진행. 진짜 10회면 `codex-round.md` 설정 변경 필요(에이전트 권한 밖).
- [ ] **BE base URL·포트·CORS 오리진** → `NEXT_PUBLIC_API_BASE_URL` 확정.
- [ ] 커밋/푸시/`git init` 여부(현재 로컬 파일 생성까지만, 규칙 5 — 명시 요청 시만).
- [ ] 실 외부 API 키(Gemini/PixVerse/fal/Wan), Supabase·R2 자격.

## 로드맵 (주차별 — 상세 각 repo docs/development-plan.md)
- 2주: 카메라·MediaPipe(FE) / Gemini 분석·서버 재검증(BE).
- 3주: 이미지 3종 생성·비교 UI(FE) / Gemini 이미지 편집(BE).
- 4주: 생성 Polling·진행 UI(FE) / PixVerse·fal·Worker 큐·Webhook·R2(BE).
- 5주: 세 모드 화면·QR·공유(FE) / 상담 저장·크레딧(BE).
- 6주: 관리자·오류/재시도·배포(양쪽).

## DB
- [ ] 실 스키마 적용/Alembic 마이그레이션(사용자 관리, §4.19). `apimgr/db/schema.sql` 참고.
