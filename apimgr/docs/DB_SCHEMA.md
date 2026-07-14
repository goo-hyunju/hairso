# apimgr — DB 스키마 설계 (정본)

> 정본 = 이 문서. `db/schema.sql` 은 이 설계의 참고용 DDL(실행 안 함). 실제 적용/마이그레이션은 사용자 관리(§4.19).
> ⚠️ 마이그레이션 실행·실 DB 변경은 이번 산출에 **포함되지 않는다**(설계·DDL 초안까지만).

## 원칙
- UUID PK(`gen_random_uuid()`). 모든 시각 `timestamptz`(ISO8601+TZ). enum = `text` + `CHECK`(D10).
- 파일은 메타데이터만(원본·공개 URL 금지, §4.13). PII(전화번호)는 암호화(`phone_enc bytea`).

## 테이블 (10)
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

## generations 핵심 컬럼 (F8 정합 — domain dataclass·Pydantic·FE Zod 와 동일 snake_case)
- `generation_type`(IMAGE/VIDEO), `provider`(6종), `status`(10종), `model`(env).
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
- `VideoProviderName`(5)·`ImageProviderName`(2)는 `contract/enums.json`·FE Zod 에만 존재하는 **파생 subset**(BE Python enum 은 `ProviderName` 6만 보유). BE parity 테스트는 이 둘을 `ProviderName` subset 으로만 검증(FE 가 정본 대조).

## 미확정
- 크레딧 잔액: 원장 합산 vs `salons.credit_balance` 캐시 컬럼(동시성 시 락 필요) — 미확정, 로드맵.
- 암호화 키 관리(phone_enc): env/KMS — 로드맵.
