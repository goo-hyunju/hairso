-- =============================================================================
-- 0001_video_mvp — 영상 생성 MVP 3테이블 (Supabase 적용용)
-- 정본 설계: docs/DB_SCHEMA.md / db/schema.sql (10테이블) 중 MVP 3테이블 축소본.
-- 변경점: consultation_id/customer_id nullable+FK제거, auth.users 참조 컬럼 추가.
-- 실행은 Supabase MCP(apply_migration)로, 사용자 승인 후에만.
-- =============================================================================

-- 1. assets -------------------------------------------------------------------
CREATE TABLE public.assets (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_type      text NOT NULL
                    CHECK (owner_type IN ('SALON_MEMBER', 'CUSTOMER', 'SYSTEM')),
    owner_id        uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    consultation_id uuid,  -- MVP: consultations 미존재 → nullable, FK 없음
    asset_type      text NOT NULL
                    CHECK (asset_type IN ('FACE_SOURCE', 'STYLE_REFERENCE',
                                          'GENERATED_IMAGE', 'GENERATED_VIDEO', 'SHARE_THUMB')),
    storage_key     text NOT NULL,
    mime_type       text NOT NULL,
    byte_size       bigint NOT NULL,
    width           int,
    height          int,
    sha256          text,
    status          text NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'EXPIRED', 'DELETED')),
    expires_at      timestamptz,   -- FACE_SOURCE=+24h / GENERATED_VIDEO=+7d (앱 세팅)
    deleted_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_assets_owner ON public.assets(owner_id);
CREATE INDEX idx_assets_expiry ON public.assets(expires_at) WHERE status = 'ACTIVE';

-- 2. generations --------------------------------------------------------------
CREATE TABLE public.generations (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id    uuid,  -- MVP: nullable, FK 없음
    created_by         uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    batch_id           uuid,  -- MVP 미사용(NULL)
    generation_type    text NOT NULL
                       CHECK (generation_type IN ('IMAGE', 'VIDEO')),
    provider           text NOT NULL
                       CHECK (provider IN ('MOCK', 'GEMINI', 'PIXVERSE',
                                           'FAL_WAN', 'WAN_CLOUD_API', 'SELF_HOSTED_WAN')),
    model              text,
    status             text NOT NULL DEFAULT 'CREATED'
                       CHECK (status IN ('CREATED', 'UPLOADING', 'SUBMITTED', 'QUEUED',
                                         'PROCESSING', 'POST_PROCESSING', 'SUCCEEDED',
                                         'FAILED', 'CANCELED', 'EXPIRED')),
    external_job_id    text,
    ai_trace_id        text,
    prompt             text,
    negative_prompt    text,
    seed               bigint,
    aspect_ratio       text,
    quality            text,
    duration_seconds   int
                       CHECK (generation_type <> 'VIDEO' OR duration_seconds IN (5, 8)),
    input_asset_id     uuid REFERENCES public.assets(id) ON DELETE SET NULL,
    output_asset_id    uuid REFERENCES public.assets(id) ON DELETE SET NULL,
    estimated_cost_usd numeric(12, 4),   -- MVP 미사용(NULL)
    actual_cost_usd    numeric(12, 4),   -- MVP 미사용(NULL)
    error_code         text,
    error_message      text,
    provider_status_raw jsonb,
    idempotency_key    text NOT NULL,
    share_token        text,             -- MVP 미사용(NULL)
    share_expires_at   timestamptz,      -- MVP 미사용(NULL)
    created_at         timestamptz NOT NULL DEFAULT now(),
    submitted_at       timestamptz,
    completed_at       timestamptz,
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (idempotency_key)
);
CREATE INDEX idx_gen_created_by ON public.generations(created_by);
CREATE INDEX idx_gen_status ON public.generations(status);
CREATE UNIQUE INDEX idx_gen_provider_job ON public.generations(provider, external_job_id)
    WHERE external_job_id IS NOT NULL;

-- 3. consents -----------------------------------------------------------------
CREATE TABLE public.consents (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id uuid,  -- MVP: nullable
    account_id      uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    customer_id     uuid,  -- MVP: customers 미존재 → nullable, FK 없음
    consent_type    text NOT NULL
                    CHECK (consent_type IN ('FACE_PROCESSING', 'EXTERNAL_AI_TRANSFER',
                                            'STORAGE', 'RESULT_SHARE')),
    granted         boolean NOT NULL,
    policy_version  text NOT NULL,
    ip_hash         text,
    user_agent      text,
    granted_at      timestamptz,
    revoked_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_consents_account ON public.consents(account_id);

-- 4. RLS: 전체 차단 (BE service_role 만 접근, FE anon 차단) ---------------------
ALTER TABLE public.assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.generations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consents ENABLE ROW LEVEL SECURITY;
-- 정책(policy) 미생성 = anon/authenticated 전체 차단. service_role 은 RLS 우회.
