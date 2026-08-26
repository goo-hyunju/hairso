-- =============================================================================
-- HairView AI — apimgr 참고용 스키마 설계(DDL 초안)
--
-- ⚠️ 실행 금지 · Alembic 마이그레이션 아님 · 실 DB 변경 아님.
--    이 파일은 설계 산출물(참고용)이다. 실제 스키마 적용/마이그레이션은
--    사용자가 직접 관리한다(루트 CLAUDE.md §0.3 / §4.19). 정본 설명은 docs/DB_SCHEMA.md.
--
-- 규칙 반영:
--   - 모든 시각은 timestamptz (ISO8601+TZ, §5.2)
--   - 핵심 상태/타입 enum 컬럼은 네이티브 ENUM 대신 text + CHECK (그린필드 값 추가·ALTER TYPE 락 회피, D10)
--     → 앱 enum ↔ CHECK 목록 동기화가 F8 게이트(값 변경 시 둘 다 갱신)
--     (예외: generations.error_code / aspect_ratio / quality 는 CHECK 미부여 — Pydantic enum·Literal 로 앱 검증)
--   - 비용(USD 원가)은 *_cost_usd, 크레딧은 credit_transactions (어휘 분리, §4.12/D11)
--   - idempotency_key UNIQUE (중복 결제/생성 방지, §4.10/D9)
--   - 파일은 메타데이터만 (원본 바이너리·공개 URL 저장 금지, §4.13)
-- =============================================================================

-- 1. salons -------------------------------------------------------------------
CREATE TABLE salons (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name          text NOT NULL,
    plan          text NOT NULL DEFAULT 'STARTER'
                  CHECK (plan IN ('STARTER', 'STANDARD', 'PRO', 'CUSTOM')),
    status        text NOT NULL DEFAULT 'ACTIVE'
                  CHECK (status IN ('ACTIVE', 'SUSPENDED')),
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- 2. salon_members (직원·인증 주체 — 자체 JWT) --------------------------------
CREATE TABLE salon_members (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    salon_id      uuid NOT NULL REFERENCES salons(id) ON DELETE CASCADE,
    email         text NOT NULL,
    password_hash text NOT NULL,                    -- 자체 JWT (§4.18)
    role          text NOT NULL DEFAULT 'STAFF'
                  CHECK (role IN ('OWNER', 'STAFF', 'ADMIN')),
    status        text NOT NULL DEFAULT 'ACTIVE'
                  CHECK (status IN ('ACTIVE', 'SUSPENDED')),
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (email)
);

-- 3. customers (PII 최소 — 전화번호 암호화, §4.13/§18) ------------------------
CREATE TABLE customers (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    salon_id      uuid REFERENCES salons(id) ON DELETE SET NULL,  -- B2C 는 NULL
    display_name  text,
    phone_enc     bytea,                            -- 암호화 저장(평문 금지)
    gender        text,
    birth_year    int,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- 4. consultations ------------------------------------------------------------
CREATE TABLE consultations (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    salon_id      uuid REFERENCES salons(id) ON DELETE SET NULL,
    customer_id   uuid REFERENCES customers(id) ON DELETE SET NULL,
    created_by    uuid REFERENCES salon_members(id) ON DELETE SET NULL,
    status        text NOT NULL DEFAULT 'OPEN'
                  CHECK (status IN ('OPEN', 'IN_PROGRESS', 'COMPLETED', 'ARCHIVED')),
    memo          text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    completed_at  timestamptz
);
CREATE INDEX idx_consultations_salon ON consultations(salon_id);

-- 5. assets (메타데이터만) ----------------------------------------------------
CREATE TABLE assets (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_type      text NOT NULL
                    CHECK (owner_type IN ('SALON_MEMBER', 'CUSTOMER', 'SYSTEM')),
    owner_id        uuid,
    consultation_id uuid REFERENCES consultations(id) ON DELETE CASCADE,
    asset_type      text NOT NULL
                    CHECK (asset_type IN ('FACE_SOURCE', 'STYLE_REFERENCE',
                                          'GENERATED_IMAGE', 'GENERATED_VIDEO', 'SHARE_THUMB')),
    storage_key     text NOT NULL,                  -- R2 key (서명 URL 아님)
    mime_type       text NOT NULL,
    byte_size       bigint NOT NULL,
    width           int,
    height          int,
    sha256          text,
    status          text NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'EXPIRED', 'DELETED')),
    expires_at      timestamptz,                    -- 참고=분석직후 / 원본=24h / 결과=7~30d (§18)
    deleted_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_assets_consultation ON assets(consultation_id);
CREATE INDEX idx_assets_expiry ON assets(expires_at) WHERE status = 'ACTIVE';

-- 6. style_references (참고 원본은 분석 후 삭제 — 이름 미저장, §6.1/§18) ------
CREATE TABLE style_references (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id    uuid NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    source_asset_id    uuid REFERENCES assets(id) ON DELETE SET NULL,
    source_type        text NOT NULL
                       CHECK (source_type IN ('UPLOAD', 'CATALOG', 'TEXT', 'AI_RECOMMEND')),
    analyzed_structure jsonb,   -- {length,bangs,parting,curl,crown_volume,side_volume,color,layer_position,overall_mood}
    source_deleted_at  timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now()
);

-- 7. style_recommendations (미모 점수화 금지, §5) -----------------------------
CREATE TABLE style_recommendations (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id     uuid NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    style_reference_id  uuid REFERENCES style_references(id) ON DELETE SET NULL,
    rank                int NOT NULL,
    title               text,
    reason              text,
    difficulty_apply    text,
    difficulty_maintain text,
    has_bangs           boolean,
    recommended_color   text,
    avoid_shape         text,
    stylist_note        text,
    structure           jsonb,
    prompt_ko           text,
    prompt_en           text,
    negative_prompt     text,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- 8. generations --------------------------------------------------------------
CREATE TABLE generations (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id    uuid NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    batch_id           uuid,                        -- 이미지 3종 묶음(영상은 NULL)
    generation_type    text NOT NULL
                       CHECK (generation_type IN ('IMAGE', 'VIDEO')),
    provider           text NOT NULL
                       CHECK (provider IN ('MOCK', 'GEMINI', 'PIXVERSE',
                                           'FAL_WAN', 'WAN_CLOUD_API',
                                           'SELF_HOSTED_WAN', 'LOCAL_SD')),
    model              text,                        -- env/Registry 관리(하드코딩 금지)
    status             text NOT NULL DEFAULT 'CREATED'
                       CHECK (status IN ('CREATED', 'UPLOADING', 'SUBMITTED', 'QUEUED',
                                         'PROCESSING', 'POST_PROCESSING', 'SUCCEEDED',
                                         'FAILED', 'CANCELED', 'EXPIRED')),
    external_job_id    text,
    ai_trace_id        text,                        -- PixVerse Ai-trace-id (외부, 내부 key 와 별도)
    prompt             text,
    negative_prompt    text,
    seed               bigint,
    aspect_ratio       text,
    quality            text,
    duration_seconds   int
                       CHECK (generation_type <> 'VIDEO' OR duration_seconds IN (5, 8)),
    input_asset_id     uuid REFERENCES assets(id) ON DELETE SET NULL,
    output_asset_id    uuid REFERENCES assets(id) ON DELETE SET NULL,
    estimated_cost_usd numeric(12, 4),              -- USD 원가(§4.12)
    actual_cost_usd    numeric(12, 4),
    error_code         text,
    error_message      text,
    provider_status_raw jsonb,
    idempotency_key    text NOT NULL,               -- 내부 중복 방지 key(§4.10)
    share_token        text,
    share_expires_at   timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    submitted_at       timestamptz,
    completed_at       timestamptz,
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (idempotency_key)                        -- 동시 중복 요청 방지(§4.10)
);
CREATE INDEX idx_gen_consultation ON generations(consultation_id);
CREATE INDEX idx_gen_status ON generations(status);
CREATE INDEX idx_gen_batch ON generations(batch_id);
CREATE UNIQUE INDEX idx_gen_share ON generations(share_token) WHERE share_token IS NOT NULL;
-- Webhook 조회 무결성: external_job_id 가 있는 행만 (provider, external_job_id) 유일.
-- 테이블 UNIQUE 는 NULL 을 서로 다르게 취급해 external_job_id NULL 행 중복을 막지 못하므로
-- 부분 유니크 인덱스로 의도(외부 job 있는 행만 유일)를 명확히 한다.
CREATE UNIQUE INDEX idx_gen_provider_job ON generations(provider, external_job_id)
    WHERE external_job_id IS NOT NULL;

-- 9. consents (동의 없으면 생성 차단 → CONSENT_REQUIRED, §3.9) -----------------
CREATE TABLE consents (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id uuid NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    customer_id     uuid REFERENCES customers(id) ON DELETE SET NULL,
    consent_type    text NOT NULL
                    CHECK (consent_type IN ('FACE_PROCESSING', 'EXTERNAL_AI_TRANSFER',
                                            'STORAGE', 'RESULT_SHARE')),
    granted         boolean NOT NULL,
    policy_version  text NOT NULL,
    ip_hash         text,                           -- 원문 IP 미저장(§18)
    user_agent      text,
    granted_at      timestamptz,
    revoked_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_consents_consultation ON consents(consultation_id);

-- 10. credit_transactions (§4.12 크레딧 원장) ---------------------------------
--   §4.12 "5분류"는 비용/크레딧 5개 개념(estimated_cost/reserved_credit/actual_cost/
--   charged_credit/refunded_credit)을 뜻한다 — tx_type(4종) 개수가 아니다.
--   매핑: estimated/actual = generations.*_cost_usd / reserved=CHARGE 전 RESERVE행 /
--         charged=CHARGE행 / refunded=REFUND행. ADJUST 는 운영 수동 보정.
CREATE TABLE credit_transactions (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    salon_id           uuid REFERENCES salons(id) ON DELETE SET NULL,
    consultation_id    uuid REFERENCES consultations(id) ON DELETE SET NULL,
    generation_id      uuid REFERENCES generations(id) ON DELETE SET NULL,
    tx_type            text NOT NULL
                       CHECK (tx_type IN ('RESERVE', 'CHARGE', 'REFUND', 'ADJUST')),
    amount_credit      numeric(12, 4) NOT NULL,     -- 크레딧(원가와 어휘 분리)
    balance_after      numeric(12, 4),
    estimated_cost_usd numeric(12, 4),
    actual_cost_usd    numeric(12, 4),
    provider           text
                       CHECK (provider IS NULL OR provider IN (
                           'MOCK', 'GEMINI', 'PIXVERSE',
                           'FAL_WAN', 'WAN_CLOUD_API', 'SELF_HOSTED_WAN', 'LOCAL_SD')),
    reason             text,
    idempotency_key    text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (idempotency_key)
);
CREATE INDEX idx_credit_generation ON credit_transactions(generation_id);

-- 11. storage_profiles (Studio 저장 위치 profile — 비밀값 저장 금지) ----------
CREATE TABLE storage_profiles (
    name             text PRIMARY KEY,
    storage_backend  text NOT NULL
                     CHECK (storage_backend IN ('LOCAL_DISK', 'SUPABASE')),
    bucket_name      text,
    base_prefix      text NOT NULL DEFAULT 'studio/outputs',
    retention_days   int NOT NULL DEFAULT 30 CHECK (retention_days > 0),
    config           jsonb NOT NULL DEFAULT '{}'::jsonb,
    is_default       boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

-- 12. studio_projects ---------------------------------------------------------
CREATE TABLE studio_projects (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    template_type        text NOT NULL
                         CHECK (template_type IN ('PROMOTION_SHORT', 'SALON_EVENT_PROMOTION')),
    category             text NOT NULL DEFAULT 'HAIR'
                         CHECK (category IN ('HAIR', 'BEAUTY', 'HEALTH', 'PRODUCT',
                                             'LOCAL_BUSINESS')),
    status               text NOT NULL DEFAULT 'DRAFTING'
                         CHECK (status IN ('DRAFTING', 'DRAFT_READY', 'RENDERING',
                                           'SUCCEEDED', 'FAILED')),
    title                text NOT NULL,
    offer_text           text NOT NULL,
    cta_text             text NOT NULL,
    duration_seconds     int NOT NULL CHECK (duration_seconds IN (15, 30)),
    target_audience      text,
    tone                 text NOT NULL DEFAULT 'FRIENDLY'
                         CHECK (tone IN ('CALM', 'TRENDY', 'PREMIUM', 'FRIENDLY')),
    disclaimer           text,
    created_by           uuid,
    storage_profile_name text NOT NULL DEFAULT 'local-dev' REFERENCES storage_profiles(name),
    render_generation_id uuid REFERENCES generations(id) ON DELETE SET NULL,
    output_asset_id      uuid REFERENCES assets(id) ON DELETE SET NULL,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_studio_projects_status ON studio_projects(status);
CREATE INDEX idx_studio_projects_render_generation ON studio_projects(render_generation_id);

-- 13. studio_project_assets ---------------------------------------------------
CREATE TABLE studio_project_assets (
    project_id  uuid NOT NULL REFERENCES studio_projects(id) ON DELETE CASCADE,
    asset_id    uuid NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
    asset_role  text NOT NULL CHECK (asset_role IN ('IMAGE', 'LOGO')),
    sort_order  int NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, asset_id, asset_role)
);
CREATE INDEX idx_studio_project_assets_asset ON studio_project_assets(asset_id);

-- 14. studio_drafts -----------------------------------------------------------
CREATE TABLE studio_drafts (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  uuid NOT NULL REFERENCES studio_projects(id) ON DELETE CASCADE,
    version     int NOT NULL CHECK (version > 0),
    script      jsonb NOT NULL,
    storyboard  jsonb NOT NULL,
    is_current  boolean NOT NULL DEFAULT true,
    created_by  uuid,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, version)
);
CREATE UNIQUE INDEX idx_studio_drafts_current
    ON studio_drafts(project_id)
    WHERE is_current = true;

-- 15. studio_render_jobs ------------------------------------------------------
CREATE TABLE studio_render_jobs (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       uuid NOT NULL REFERENCES studio_projects(id) ON DELETE CASCADE,
    generation_id    uuid NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    draft_version    int NOT NULL,
    idempotency_key  text NOT NULL,
    status           text NOT NULL DEFAULT 'SUBMITTED'
                     CHECK (status IN ('SUBMITTED', 'PROCESSING', 'SUCCEEDED', 'FAILED',
                                       'CANCELED', 'EXPIRED')),
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (idempotency_key),
    UNIQUE (generation_id)
);
CREATE UNIQUE INDEX idx_studio_render_jobs_one_active
    ON studio_render_jobs(project_id)
    WHERE status IN ('SUBMITTED', 'PROCESSING');
