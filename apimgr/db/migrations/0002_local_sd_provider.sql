-- =============================================================================
-- 0002_local_sd_provider — generations.provider 에 'LOCAL_SD' 허용 추가
-- 목적: 로컬 자체호스팅 SD inpainting(이미지) Provider(§4.8) 를 generations 에 기록 가능하게.
-- 성격: 비파괴(additive) — 허용값 1개 추가일 뿐, 기존 행은 모두 제약을 만족한다.
-- 계약 동기화: domain/enums.py ProviderName + contract/enums.json + FE schemas.ts (parity 테스트 통과).
-- 실행은 Supabase MCP(apply_migration)로, 사용자 승인 후에만(§4.19).
-- =============================================================================

ALTER TABLE public.generations DROP CONSTRAINT IF EXISTS generations_provider_check;

ALTER TABLE public.generations ADD CONSTRAINT generations_provider_check
    CHECK (provider IN (
        'MOCK', 'GEMINI', 'PIXVERSE', 'FAL_WAN', 'WAN_CLOUD_API', 'SELF_HOSTED_WAN', 'LOCAL_SD'
    ));
