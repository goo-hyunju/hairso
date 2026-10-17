# TASKS — 다음 단계 작업 목록

## 완료
- [x] FE+BE 스캐폴드(빌드·테스트 통과), 문서군, 도메인/스키마 설계, Mock Provider, 계약 parity.
- [x] Studio MVP 기획 보강: 첫 템플릿을 Hair Styling(헤어 연출)으로 확정하고 mock project→draft→edit→render 방향 문서화.
- [x] Docker 개발 실행 초안 추가: FE/BE dev compose, Dockerfile.dev, .dockerignore.

## 사용자 확인 필요 (블로킹)
- [x] **로컬 BE base URL·포트·CORS 오리진** → 해소. dev 는 FE `next.config.mjs` 프록시(`/api/*` → BE `127.0.0.1:8000`)를 사용하고 CORS는 쓰지 않는다.
- [ ] **운영 게이트웨이/CORS 오리진** 확정.
- [x] 에이전트 설정·규칙 파일(.claude/.codex/.agents/.ai·CLAUDE.md·AGENTS.md): 저장소 제외 + 이력 재작성으로 과거 커밋에서도 제거(로컬 전용).
- [x] Supabase project ref·과거 IP/개인 경로 문자열의 이력 잔존(시크릿 아님, HEAD 는 placeholder) — 사용자 결정 완료(2026-10-17): 추가 재작성하지 않고 공개.
- [ ] 실 외부 API 키(Gemini/PixVerse/fal/Wan), Supabase·R2 자격.

## 보안 선행 작업 (실 Provider/실 고객 이미지 전 필수)
- [ ] `GET /api/v1/assets/{asset_id}/content`에 상담 단위 권한, 공유 토큰, 만료 정책 적용. 현재는 인증된 `owner_id` 일치만 허용한다.
- [ ] 생성 요청 전 asset 존재·상태·소유권·동의 확인. 현재: 저수준 `POST /video-generations` 는 non-Mock 경로에서만 소유권 확인(`generations.py`), Studio 는 프로젝트 생성 시 asset 존재·상태·타입·소유 검사 후 렌더 시 바이트 로딩(`studio_service.py`; 소유자 없는 asset 은 누구나 참조 가능, 익명 GENERATED_IMAGE 는 Studio 입력 금지). 동의(consent) 검사는 전 경로 미구현.
- [ ] PixVerse webhook을 payload schema 검증과 DB 기반 event 중복 처리로 보강. 현재는 server clock freshness와 secret fail-closed만 적용되어 있다.

## Studio MVP 다음 작업
- [x] BE `studio` project/draft schema 추가(Mock-first, in-memory).
- [x] BE mock draft service 추가: Salon Event Promotion script/storyboard 결정적 생성.
- [x] BE Studio draft provider 분리: `MOCK` 기본 + backend-only local `OLLAMA` 옵션, 실패 시 Mock fallback.
- [x] BE render endpoint가 기존 generation job을 재사용하도록 연결.
- [x] BE `SELF_HOSTED_WAN` 로컬 MP4 provider opt-in 추가: ml job 등록→폴링→`/output` MP4 를 `GENERATED_VIDEO`로 저장. 조회발 lazy advance 추가(실효 조건: `DATABASE_URL` 영속·Studio 0003·ml job 생존·동일 `DEFAULT_VIDEO_PROVIDER`; 인메모리 기본에서는 재시작 복원 없음).
- [x] FE `/studio` 작업 화면 추가: 입력, 초안 편집, 9:16 preview, render 시작.
- [x] FE `/studio`가 기존 generation status polling을 재사용.
- [ ] Compose smoke를 실제로 실행해 `http://localhost:3000/studio`와 `/try`가 함께 동작하는지 확인.
- [x] Wan 2.2 TI2V-5B 를 `ml/wan_video.py` 로 diffusers 직접 통합(`LOCAL_VIDEO_RENDER_COMMAND` 는 대체 경로). 실측표는 README(작성자 보고, 자동 검증 없음).
- [ ] ml job 메모리 TTL 도입(`serve.py` `_video_jobs` 무제한 보관).
- [ ] aspect_ratio 1:1 / quality 1080p 가 ml 에서 9:16 / 480p 로 강등되는 문제 — 스키마 축소 또는 ml 구현.
- [ ] 라우터 내 폴링·전진 로직(`generations.py`, `studio.py` 중복)을 Worker 계층으로 이동.
- [ ] FE: 렌더 진행 안내 문구를 provider 에 따라 분기(`StudioWorkspace.tsx`, Mock 에서도 로컬 GPU 기준 소요시간 노출).
- [ ] 검증 스크립트 `verify_local_image.py`: `FACE_SRC`(미추적 `ml/test_face.jpg`) 의존, JPG 바이트를 `image/png` 로 저장하는 결함, stdout 경로 출력 정리.
- [ ] 렌더 프롬프트 지시 충돌 정리: 템플릿 "Preserve face identity" vs 공통 제약 "do not depict any real person's face"(`studio_service.py`).
- [ ] lazy advance 상호 배제: 백그라운드 폴러도 `_advance_inflight` 에 등록(`generations.py`, `studio.py`).
- [ ] 동시 요청 멱등성: ml `/video/i2v` check-then-act(`serve.py`), Studio render 프로젝트 단위 잠금.
- [ ] 실패 후 재렌더·편집 후 재렌더 허용(`studio_service.py` 기존 generation 무조건 반환, FE `render_generation_id` 잠금).
- [ ] `GET /generations/{id}` 소유권 확인.
- [ ] generations 에 duration/aspect_ratio/quality/seed 영속 + VIDEO CHECK 확장(5/8 → Studio 5/15/30).
- [ ] `self_hosted_wan` HTTP 오류 재시도(지수 백오프, 규칙 §4.17) — 현재 1회 오류로 FAILED.
- [ ] lazy advance 가 저장된 `gen.provider` 와 현재 `DEFAULT_VIDEO_PROVIDER` 가 다르면 전진을 생략하도록 보강(`generations.py`).
- [ ] 만료 에셋 자동 삭제 Worker(`expires_at` 기록만 있고 삭제 코드 없음).
- [ ] 원격 GPU 구성(BE 와 ml 분리) 허용 여부 결정 — 현재 로컬 호스트만 허용.

## 로드맵 (주차별 — 상세 각 repo docs/development-plan.md)
- 2주: Studio Event Promotion Mock flow / 카메라·MediaPipe(FE) / Gemini 분석·서버 재검증(BE).
- 3주: 이미지 3종 생성·비교 UI(FE) / Gemini 이미지 편집(BE).
- 4주: 생성 Polling·진행 UI(FE) / PixVerse·fal·Worker 큐·Webhook·R2(BE).
- 5주: 세 모드 화면·QR·공유(FE) / 상담 저장·크레딧(BE).
- 6주: 관리자·오류/재시도·배포(양쪽).

## DB
- [ ] SQL 마이그레이션 실행 상태 확인(사용자 관리, §4.19): 0001 적용(문서 기준), 0002 미확인, 0003 미적용. `apimgr/db/migrations/`.
