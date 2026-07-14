# ARCHITECTURE — HairView AI

## 저장소
```
hairso/
  hairsoui/   FE — Next.js App Router · React · TS strict · Tailwind v4 (독립 저장소)
  apimgr/     BE — Python · FastAPI · Pydantic (독립 저장소)
  docs/       교차 문서 (본 폴더)
```
> ⚠️ 기획서 §10/§23 은 BE 를 TypeScript 로 적었으나, 루트 CLAUDE.md(이 저장소 절대 규칙)가 BE=Python·FastAPI 로 규정 → **규칙 우선**. 기획서 TS BE 서술은 미채택(§0.7).

## 흐름
```
[고객 휴대폰 · 미용실 태블릿]
        │  (반응형 웹 — 한 코드베이스)
   [Next.js Web (hairsoui)]  카메라·상담 UI·결과 공유
        │  REST (/api/v1, snake_case, JWT)
   [FastAPI (apimgr)]  인증·분석·생성요청 (Router→Service→Repository/Provider)
        │
  Supabase(PostgreSQL) · Gemini · Generation Queue
        │
  PixVerse / fal Wan / Wan Cloud  →  Webhook  →  FFmpeg Worker  →  Cloudflare R2  →  결과 링크·QR
```
FE 는 외부 AI 를 직접 호출하지 않는다: `FE → apimgr → Provider → apimgr → FE`.

## 비동기 생성
`POST /api/v1/video-generations → 202 + generation_id` → Worker 가 Provider 폴링/Webhook → 상태 전이(10종) → 다운로드 → R2 → FFmpeg → 완료. FE 는 `GET /api/v1/generations/{id}` Polling.

## 상태 레이어
외부 `ProviderJobStatus`(4) → 내부 `GenerationStatus`(10) 매핑(status_mapping) → state_machine(타입별, no-op 멱등). 전이는 한 곳 관리(§4.16).

## 스캐폴드 실장 vs 로드맵
실장: 계층 골격·Mock Provider·상태머신·계약·202 흐름. 로드맵: 실 Provider·실 DB·Worker 큐·FFmpeg·R2. 상세 [`LABELS.md`](./LABELS.md).
