# apimgr — DB 스키마 설계 (정본)

> 정본 = 이 문서. `db/schema.sql` 은 전체 10테이블 + Studio 확장 5테이블 참고용 DDL. 실제 적용/마이그레이션은 사용자 관리(§4.19).
>
> **영상 MVP 적용 상태(2026-07-14):** `assets`·`generations`·`consents` **3테이블을 Supabase(project_ref=gtbdiiunozsbbdajmick)에 적용함.**
> 마이그레이션: `db/migrations/0001_video_mvp.sql`. 변경점: `consultation_id`/`customer_id` nullable+FK제거, `auth.users` 참조(`owner_id`/`created_by`/`account_id`), RLS 전체차단(정책 0개 = BE service_role 만 접근), Storage private bucket `hairview-assets`.
> 나머지 7테이블(salons/salon_members/customers/consultations/style_references/style_recommendations/credit_transactions)은 **로드맵 유지**(미적용). 상세 설계·계획: `docs/superpowers/specs/2026-07-14-video-mvp-db-schema-design.md`, `docs/superpowers/plans/2026-07-14-video-mvp-db-schema.md`.
>
> **Studio MVP 확장 상태:** `db/migrations/0003_studio_mvp.sql` 추가. `storage_profiles`·`studio_projects`·`studio_project_assets`·`studio_drafts`·`studio_render_jobs` 설계만 생성했으며 실제 DB에는 적용하지 않았다.

## 원칙
- UUID PK(`gen_random_uuid()`). 모든 시각 `timestamptz`(ISO8601+TZ). enum = `text` + `CHECK`(D10).
- 파일은 메타데이터만(원본·공개 URL 금지, §4.13). PII(전화번호)는 암호화(`phone_enc bytea`).

## 테이블 (기본 10)
1. **salons** — 미용실. plan(STARTER/STANDARD/PRO/CUSTOM).
2. **salon_members** — 직원·인증 주체(자체 JWT, `password_hash`). role(OWNER/STAFF/ADMIN).
3. **customers** — 고객. `phone_enc`(암호화). B2C 는 salon_id NULL.
4. **consultations** — 상담. status(OPEN/IN_PROGRESS/COMPLETED/ARCHIVED).
5. **assets** — 파일 메타데이터. asset_type, storage_key(R2), expires_at(만료 정책 §18).
6. **style_references** — 참고 사진 분석. `analyzed_structure jsonb`(헤어 구조만, 이름 미저장). 원본은 분석 후 삭제.
7. **style_recommendations** — 추천 3종. prompt_ko/en, negative_prompt. 미모 점수 없음.
8. **generations** — 생성 작업(§14 + 보강). 아래 상세.
9. **consents** — 동의(FACE_PROCESSING/EXTERNAL_AI_TRANSFER/STORAGE/RESULT_SHARE). 없으면 CONSENT_REQUIRED.
10. **credit_transactions** — 크레딧 원장(RESERVE/CHARGE/REFUND/ADJUST).

## Studio 확장 테이블 (5)
1. **storage_profiles** — 저장 위치 profile. backend, bucket, base_prefix, retention_days. secret 저장 금지.
2. **studio_projects** — Studio 제품 프로젝트. template, category, brief, 최종 길이(15/30), 현재 render/output 참조.
3. **studio_project_assets** — 프로젝트에 연결된 이미지/로고 asset 목록. role(IMAGE/LOGO).
4. **studio_drafts** — script/storyboard 편집본 version. current partial unique.
5. **studio_render_jobs** — project와 기존 generations job 연결. idempotency_key unique.

## generations 핵심 컬럼 (F8 정합 — domain dataclass·Pydantic·FE Zod 와 동일 snake_case)
- `generation_type`(IMAGE/VIDEO), `provider`(7종), `status`(10종), `model`(env).
- `external_job_id` + `ai_trace_id`(PixVerse 외부, 내부 `idempotency_key` 와 별도, §13).
- `batch_id`(이미지 3종 묶음, 인덱스), `share_token`(부분 UNIQUE).
- `estimated_cost_usd`/`actual_cost_usd`(numeric). `idempotency_key` **UNIQUE**(§4.10).
- 제약: `UNIQUE(idempotency_key)`, `UNIQUE(provider, external_job_id)`, VIDEO 만 `duration ∈ {5,8}` CHECK.

## 크레딧 5분류 매핑 (§4.12 / D11)
| 개념 | 위치 |
|---|---|
| estimated_cost | generations.estimated_cost_usd |
| actual_cost | generations.actual_cost_usd |
| reserved_credit | credit_transactions tx_type=RESERVE |
| charged_credit | tx_type=CHARGE |
| refunded_credit | tx_type=REFUND |

## 설계 각주
- `CreditTxType` = RESERVE/CHARGE/REFUND + **ADJUST**(수동 보정용, §4.12 5분류 외 운영 보정). 세 파일(enums.py·enums.json·schema.sql) 일관.
- `assets.owner_id` 는 폴리모픽(`owner_type` + `owner_id`)이라 DB FK 미강제 — 참조무결성은 앱 레벨 보장(MVP 허용).
- `provider/generation_type/status/tx_type/plan/role/consent_type/asset_type` 은 text+CHECK. `error_code/aspect_ratio/quality` 는 CHECK 미부여(Pydantic 층에서 enum·Literal 검증) — 실 DB 도입(로드맵) 시 CHECK 추가 검토.
- `VideoProviderName`(5)·`ImageProviderName`(3)는 `contract/enums.json`·FE Zod 에만 존재하는 **파생 subset**(BE Python enum 은 `ProviderName` 7개 보유). BE parity 테스트는 이 둘을 `ProviderName` subset 으로만 검증(FE 가 정본 대조).

## 미확정
- 크레딧 잔액: 원장 합산 vs `salons.credit_balance` 캐시 컬럼(동시성 시 락 필요) — 미확정, 로드맵.
- 암호화 키 관리(phone_enc): env/KMS — 로드맵.
