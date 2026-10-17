-- =============================================================================
-- 0003_studio_mvp — Studio project/draft/render 확장 DDL
--
-- ⚠️ 실행 금지 · 사용자 승인 후에만 적용.
--    이 파일은 확장 가능한 Studio DB 구조를 고정하기 위한 migration 초안이다.
--    실제 적용 전 기존 0001/0002 적용 상태와 constraint drift 를 확인해야 한다.
--
-- 설계:
--   - Studio 최종 길이(5/15/30초)는 studio_projects.duration_seconds 에 저장한다.
--   - 기존 generations.duration_seconds(5/8초)는 provider scene clip 계약으로 유지한다.
--   - signed URL, 원본 storage key, provider raw payload 는 API 응답에 노출하지 않는다.
--   - storage_profiles 는 비밀 없는 저장 위치/profile 메타만 저장한다. secret 은 env/secret manager.
-- =============================================================================

-- 1. storage_profiles ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.storage_profiles (
    name             text PRIMARY KEY,
    storage_backend  text NOT NULL
                     CHECK (storage_backend IN ('LOCAL_DISK', 'SUPABASE')),
    bucket_name      text,
    base_prefix      text NOT NULL DEFAULT 'studio/outputs',
    retention_days   int NOT NULL DEFAULT 30 CHECK (retention_days > 0),
    config           jsonb NOT NULL DEFAULT '{}'::jsonb, -- 비밀값 저장 금지
    is_default       boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.storage_profiles
    (name, storage_backend, bucket_name, base_prefix, retention_days, is_default)
VALUES
    ('local-dev', 'LOCAL_DISK', NULL, 'studio/outputs', 30, true)
ON CONFLICT (name) DO NOTHING;

-- 2. studio_projects ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.studio_projects (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    template_type        text NOT NULL
                         CHECK (template_type IN ('HAIR_STYLING_MOTION', 'PROMOTION_SHORT',
                                                  'SALON_EVENT_PROMOTION', 'FREE_IMAGE_TO_VIDEO')),
    category             text NOT NULL DEFAULT 'HAIR'
                         CHECK (category IN ('HAIR', 'BEAUTY', 'HEALTH', 'PRODUCT',
                                             'LOCAL_BUSINESS', 'PET', 'GENERAL')),
    status               text NOT NULL DEFAULT 'DRAFTING'
                         CHECK (status IN ('DRAFTING', 'DRAFT_READY', 'RENDERING',
                                           'SUCCEEDED', 'FAILED')),
    title                text NOT NULL,
    offer_text           text NOT NULL,
    cta_text             text NOT NULL,
    duration_seconds     int NOT NULL CHECK (duration_seconds IN (5, 15, 30)),
    target_audience      text,
    tone                 text NOT NULL DEFAULT 'FRIENDLY'
                         CHECK (tone IN ('CALM', 'TRENDY', 'PREMIUM', 'FRIENDLY')),
    disclaimer           text,
    created_by           uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    storage_profile_name text NOT NULL DEFAULT 'local-dev'
                         REFERENCES public.storage_profiles(name),
    render_generation_id uuid REFERENCES public.generations(id) ON DELETE SET NULL,
    output_asset_id      uuid REFERENCES public.assets(id) ON DELETE SET NULL,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_studio_projects_created_by
    ON public.studio_projects(created_by);
CREATE INDEX IF NOT EXISTS idx_studio_projects_status
    ON public.studio_projects(status);
CREATE INDEX IF NOT EXISTS idx_studio_projects_render_generation
    ON public.studio_projects(render_generation_id);

-- 3. studio_project_assets ----------------------------------------------------
CREATE TABLE IF NOT EXISTS public.studio_project_assets (
    project_id  uuid NOT NULL REFERENCES public.studio_projects(id) ON DELETE CASCADE,
    asset_id    uuid NOT NULL REFERENCES public.assets(id) ON DELETE RESTRICT,
    asset_role  text NOT NULL CHECK (asset_role IN ('IMAGE', 'LOGO')),
    sort_order  int NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, asset_id, asset_role)
);
CREATE INDEX IF NOT EXISTS idx_studio_project_assets_asset
    ON public.studio_project_assets(asset_id);

-- 4. studio_drafts ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.studio_drafts (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  uuid NOT NULL REFERENCES public.studio_projects(id) ON DELETE CASCADE,
    version     int NOT NULL CHECK (version > 0),
    script      jsonb NOT NULL,
    storyboard  jsonb NOT NULL,
    is_current  boolean NOT NULL DEFAULT true,
    created_by  uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, version)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_studio_drafts_current
    ON public.studio_drafts(project_id)
    WHERE is_current = true;

-- 5. studio_render_jobs -------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.studio_render_jobs (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       uuid NOT NULL REFERENCES public.studio_projects(id) ON DELETE CASCADE,
    generation_id    uuid NOT NULL REFERENCES public.generations(id) ON DELETE CASCADE,
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
CREATE INDEX IF NOT EXISTS idx_studio_render_jobs_project
    ON public.studio_render_jobs(project_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_studio_render_jobs_one_active
    ON public.studio_render_jobs(project_id)
    WHERE status IN ('SUBMITTED', 'PROCESSING');

-- 6. RLS: FE direct 접근 차단, BE service_role 경유 --------------------------
ALTER TABLE public.storage_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.studio_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.studio_project_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.studio_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.studio_render_jobs ENABLE ROW LEVEL SECURITY;
-- 정책(policy) 미생성 = anon/authenticated 전체 차단. service_role 은 RLS 우회.
