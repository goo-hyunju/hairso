# 영상 생성 MVP — Supabase DB 스키마 설계 (spec)

> 작성일: 2026-07-14
> 상태: 승인됨(설계). 실제 Supabase 적용은 별도 승인 후 진행.
> 정본 참조: `apimgr/docs/DB_SCHEMA.md`(전체 10테이블 설계), `apimgr/db/schema.sql`(참고 DDL).
> 이 문서는 그 정본을 **영상 MVP 범위(3테이블)로 축소·Supabase 특화**한 파생 설계다.

## 1. 목적·범위

기존 10테이블 설계(일반 PostgreSQL + Cloudflare R2 + 자체 JWT 전제)를 재검토하여,
**"AI로 영상 만들기" MVP**에 필요한 최소 스키마만 Supabase에 적용한다.

### MVP 스코프

| 항목 | 결정 |
|------|------|
| 목표 | AI 영상 생성 한 줄기(vertical slice) 검증 |
| 테이블 | `generations`, `assets`, `consents` (3개) |
| 인증 | Supabase Auth (`auth.users`) |
| 파일 저장 | Supabase Storage (private bucket) |
| 결과물 | 다운로드형(핸드폰 로컬 보관). 공유 링크/QR 없음 |
| 과금 | 없음. 중복 생성만 `idempotency_key` UNIQUE로 방지 |
| 보관 기간 | 입력 얼굴 사진 24시간 / 결과 영상 7일 |

### 로드맵으로 미루는 것 (이번 미포함)

- 테이블: `salons`, `salon_members`, `customers`, `consultations`, `style_references`, `style_recommendations`, `credit_transactions`
- 기능: 조직/멀티테넌트, 고객 관리, 스타일 분석·추천, 크레딧·과금, 결과 공유 링크

## 2. 인증·소유권 모델

MVP엔 조직/직원 테이블이 없으므로 **소유자 = 로그인한 Supabase 계정**이다.

- 로그인 주체: `auth.users` (Supabase Auth 관리 스키마)
- 소유권 참조: `generations.created_by`, `assets.owner_id`, `consents.account_id` → `auth.users(id)`
- 확장 대비: 나중에 조직을 붙일 때 각 테이블에 `salon_id` 컬럼만 추가하면 되도록 설계(재작업 최소)

### 데이터 접근 경로 (프로젝트 규칙 §3.4)

```
FE ──(로그인/토큰 발급만)──▶ Supabase Auth        # supabase-js
FE ──(데이터/생성/업로드)──▶ FastAPI(BE) ──▶ Supabase DB · Storage · AI Provider
```

- FE는 **로그인만** Supabase 직접 호출. 테이블 CRUD·영상 생성·파일 업로드는 **전부 BE 경유**.
- 따라서 RLS(Row Level Security, 행 단위 접근제어)는 **기본 전체 차단**.
  BE는 `service_role` 키(RLS 우회 관리자 키)로 접근. FE의 anon 키로는 테이블·스토리지에 직접 접근 불가.
- 근거: 얼굴 사진·생성물 무단 노출 방지(프로젝트 규칙 §11 최우선순위).

## 3. 테이블 설계

정본 `db/schema.sql` 대비 **변경점만** 명시한다. 명시 없는 컬럼은 정본과 동일.

### 3.1 assets — 파일 메타데이터

정본 유지. 변경점:

- `consultation_id` → **nullable, FK 제거**(consultations 테이블 없음)
- `owner_id` → `auth.users(id)` 참조로 명확화(정본은 폴리모픽 FK 미강제)
- `expires_at` 세팅 규칙(앱 레벨):
  - `asset_type='FACE_SOURCE'` → `created_at + 24h`
  - `asset_type='GENERATED_VIDEO'` → `created_at + 7d`
- MVP에서 실제 사용하는 `asset_type`: `FACE_SOURCE`, `GENERATED_VIDEO`(나머지 값은 CHECK에 유지하되 미사용)

### 3.2 generations — 생성 작업 (MVP 핵심)

정본 완성형 컬럼을 거의 그대로 유지. 변경점:

- `consultation_id` → **nullable, FK 제거**
- `created_by uuid REFERENCES auth.users(id)` **추가**
- `idempotency_key text NOT NULL UNIQUE` **유지**(중복 영상 생성/결제 방지 — 최우선, §4.10)
- MVP는 `generation_type='VIDEO'` 행만 사용
- **컬럼은 두되 MVP 미사용(NULL)**: `share_token`, `share_expires_at`, `batch_id`,
  `estimated_cost_usd`, `actual_cost_usd`
- 상태 흐름은 기존 `domain/state_machine.py`·`domain/status_mapping.py` **재사용**:
  ```
  CREATED → UPLOADING → SUBMITTED → QUEUED → PROCESSING → POST_PROCESSING → SUCCEEDED
     (각 단계) → FAILED / CANCELED / EXPIRED
  ```
- 제약 유지: `UNIQUE(idempotency_key)`,
  부분 유니크 `UNIQUE(provider, external_job_id) WHERE external_job_id IS NOT NULL`,
  VIDEO만 `duration_seconds ∈ {5,8}` CHECK

### 3.3 consents — 동의

정본 유지. 변경점:

- `consultation_id` → **nullable**
- `account_id uuid REFERENCES auth.users(id)` **추가**
- MVP 확인 로직: 생성 요청 직전 **`EXTERNAL_AI_TRANSFER`(외부 AI 전송) 동의**가 유효(`granted=true`, 미철회)해야 함.
  없으면 `CONSENT_REQUIRED` 오류로 생성 차단(§3.9).

## 4. 스토리지·보안(RLS)

- Supabase **private bucket** 1개(예: `hairview-assets`). 경로 규칙: `face/{uuid}`, `video/{uuid}`
- `assets`·`generations`·`consents` 3테이블 + `storage.objects`에 **RLS 활성화 + 정책 없음 = 전체 차단**
- BE만 `service_role` 키로 읽기/쓰기
- FE에는 결과 영상 **다운로드용 서명 URL**(짧은 만료)만 발급. 사용자가 받으면 핸드폰 로컬 보관

## 5. 코드 영향 (구현 단계에서 처리 — 이번 범위 아님)

- `apimgr/app/domain/models.py`에 `Asset`, `Consent` dataclass 추가(현재 `Generation`/`CreditTransaction`만 존재)
- Repository(현재 in-memory 스캐폴드)를 Supabase 접근으로 교체 — **별도 구현 단계**로 분리
- MVP 미사용 컬럼(share/cost/batch)은 domain 모델에도 유지(정합)

## 6. 적용 절차 (승인 후 실행)

1. Supabase MCP 인증(OAuth) — 실제 프로젝트/테이블 현황 확인
2. 실 DB에 테이블 없음 확인 후, MVP 3테이블 마이그레이션 SQL 준비
3. **사용자 승인 후** 마이그레이션 실행(§4.19: 스키마 자동 변경 금지)
4. bucket 생성 + RLS 정책 적용
5. 적용 결과 검증(테이블·제약·인덱스·RLS 상태 확인)

## 7. 미확정·주의

- `auth.users` 참조 FK: Supabase에서 `auth` 스키마 참조 방식·`ON DELETE` 정책 확정 필요(적용 단계에서 검증)
- 암호화 키 관리(향후 `customers.phone_enc`): 로드맵
- 크레딧 잔액 캐시 vs 원장 합산: 로드맵(과금 도입 시)
- 만료 자동 삭제(24h/7d)를 수행하는 주체(Worker/Supabase cron): 구현 단계에서 결정
