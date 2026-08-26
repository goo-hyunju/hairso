# TASKS — 다음 단계 작업 목록

## 이번 산출(완료)
- [x] FE+BE 스캐폴드(빌드·테스트 통과), 문서군, 도메인/스키마 설계, Mock Provider, 계약 parity.
- [x] Studio MVP 부족 기획 보강: 첫 템플릿을 Salon Event Promotion으로 확정하고 mock project→draft→edit→render 방향 문서화.
- [x] Docker 개발 실행 초안 추가: FE/BE dev compose, Dockerfile.dev, .dockerignore.

## 사용자 확인 필요 (블로킹)
- [ ] **Codex ROUND 상한**: 사용자 지시 "10라운드" vs 규칙(codex-round.md) "최대 3회". 이번은 3회 진행. 진짜 10회면 `codex-round.md` 설정 변경 필요(에이전트 권한 밖).
- [x] **로컬 BE base URL·포트·CORS 오리진** → 해소. dev 는 FE `next.config.mjs` 프록시(`/api/*` → BE `127.0.0.1:8000`)를 사용하고 CORS는 쓰지 않는다.
- [ ] **운영 게이트웨이/CORS 오리진** 확정.
- [ ] 커밋/푸시/`git init` 여부(현재 로컬 파일 생성까지만, 규칙 5 — 명시 요청 시만).
- [ ] 실 외부 API 키(Gemini/PixVerse/fal/Wan), Supabase·R2 자격.

## 보안 선행 작업 (실 Provider/실 고객 이미지 전 필수)
- [ ] `GET /api/v1/assets/{asset_id}/content`에 상담 단위 권한, 공유 토큰, 만료 정책 적용. 현재는 인증된 `owner_id` 일치만 허용한다.
- [ ] 생성 요청 전 asset 존재·상태·소유권·동의 확인.
- [ ] PixVerse webhook을 payload schema 검증과 DB 기반 event 중복 처리로 보강. 현재는 server clock freshness와 secret fail-closed만 적용되어 있다.

## 로드맵 (주차별 — 상세 각 repo docs/development-plan.md)
## Studio MVP 다음 작업
- [x] BE `studio` project/draft schema 추가(Mock-first, in-memory).
- [x] BE mock draft service 추가: Salon Event Promotion script/storyboard 결정적 생성.
- [x] BE Studio draft provider 분리: `MOCK` 기본 + backend-only local `OLLAMA` 옵션, 실패 시 Mock fallback.
- [x] BE render endpoint가 기존 generation job을 재사용하도록 연결.
- [x] BE `SELF_HOSTED_WAN` 로컬 MP4 provider opt-in 추가: 로컬 `/video/i2v` 응답 바이트를 `GENERATED_VIDEO`로 저장.
- [x] FE `/studio` 작업 화면 추가: 입력, 초안 편집, 9:16 preview, render 시작.
- [x] FE `/studio`가 기존 generation status polling을 재사용.
- [ ] Compose smoke를 실제로 실행해 `http://localhost:3000/studio`와 `/try`가 함께 동작하는지 확인.
- [ ] 로컬 Wan/CogVideoX/ComfyUI 명령을 `ml/serve.py`의 `LOCAL_VIDEO_RENDER_COMMAND`에 연결해 샘플 MP4 생성 시간과 VRAM을 측정.

## 로드맵 (주차별 — 상세 각 repo docs/development-plan.md)
- 2주: Studio Event Promotion Mock flow / 카메라·MediaPipe(FE) / Gemini 분석·서버 재검증(BE).
- 3주: 이미지 3종 생성·비교 UI(FE) / Gemini 이미지 편집(BE).
- 4주: 생성 Polling·진행 UI(FE) / PixVerse·fal·Worker 큐·Webhook·R2(BE).
- 5주: 세 모드 화면·QR·공유(FE) / 상담 저장·크레딧(BE).
- 6주: 관리자·오류/재시도·배포(양쪽).

## DB
- [ ] 실 스키마 적용/Alembic 마이그레이션(사용자 관리, §4.19). `apimgr/db/schema.sql` 참고.
