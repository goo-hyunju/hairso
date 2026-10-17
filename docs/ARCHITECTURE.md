# ARCHITECTURE — Hairso Studio

## 저장소 (루트 단일 Git 모노레포)
```
hairso/
  hairsoui/   FE — Next.js App Router · React · TS strict · Tailwind v4
  apimgr/     BE — Python · FastAPI · Pydantic
  ml/         로컬 GPU 추론 서비스(opt-in) — SD1.5 inpaint 리스타일 · Wan 2.2 TI2V-5B 영상
  docs/       교차 문서 (본 폴더)
  docker-compose.dev.yml
```
> ⚠️ 초기 기획서는 BE 를 TypeScript 로 적었으나, 프로젝트 규칙이 BE=Python·FastAPI 로 규정 → **규칙 우선**. 기획서 TS BE 서술은 미채택.

## 흐름 (실선 = 구현, 점선 = 로드맵)
```
[휴대폰 · 태블릿 · PC 브라우저]  (반응형 웹 — 한 코드베이스)
        │
   [Next.js (hairsoui)]  /api/* 프록시 → BE. Studio 4단계 UI, 상태 폴링
        │  REST /api/v1 (snake_case), Bearer 토큰은 선택(없으면 익명)
   [FastAPI (apimgr)]  Router → Service → Repository / Provider
        ├── Mock Provider (기본: 분석·이미지·영상·초안)
        ├── opt-in: ml/serve.py (:8188)  POST /restyle · POST /video/i2v job
        ├── opt-in: Ollama (초안 텍스트)
        ├── 저장: LOCAL_DISK (기본) · Supabase Storage (opt-in)
        └── DB: 인메모리 (기본) · Supabase Postgres (DATABASE_URL 설정 시)
        ┆
        ┆ 로드맵: PixVerse(스텁) · fal Wan · Wan Cloud · Gemini · Worker 큐 · FFmpeg 후처리 · R2 · 공유 링크/QR
```
FE 는 외부 AI 를 직접 호출하지 않는다: `FE → apimgr → Provider → apimgr → FE`.

## 비동기 생성
`POST /api/v1/video-generations` 또는 `POST /api/v1/studio/projects/{id}/render` → `202 + generation_id` → 데모용 BackgroundTasks 폴러가 Provider 상태를 폴링 → 상태 전이(10종) → 결과 바이트 저장(`GENERATED_VIDEO`) → `SUCCEEDED`. FE 는 `GET /api/v1/generations/{id}` 를 1.2초 간격으로 폴링한다.
BE 가 재시작돼 폴러가 사라진 경우의 복원(lazy advance)은 다음 조건에서만 동작한다 — ① `DATABASE_URL` 로 generation·project 메타가 영속돼 있을 것(Studio 경로는 0003 적용 포함), ② ml 서버의 job 이 살아 있을 것(ml 재시작 시 FAILED), ③ 재시작 후에도 같은 `DEFAULT_VIDEO_PROVIDER` 설정일 것(조회 시 저장된 provider 가 아니라 현재 기본 Provider 로 ml 을 조회한다), ④ Mock Provider 는 대상 아님. 기본 인메모리 저장소에서는 재시작 시 작업 정보가 사라진다. 실 Worker 큐·FFmpeg·R2 는 로드맵.

## 상태 레이어
외부 `ProviderJobStatus`(4) → 내부 `GenerationStatus`(10) 매핑(status_mapping) → state_machine(타입별, no-op 멱등). 전이는 한 곳 관리.

## 구현 vs 로드맵
상세 라벨은 [`LABELS.md`](./LABELS.md). 요약: 계층 골격·Mock Provider·상태머신·계약·202 흐름·Studio MVP·로컬 AI opt-in 은 구현, 실 외부 Provider·Worker 큐·FFmpeg·R2·크레딧·공유는 로드맵.
