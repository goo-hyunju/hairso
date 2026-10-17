# 영상 생성 MVP — Supabase DB 스키마 적용 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 영상 생성 MVP에 필요한 3테이블(`generations`/`assets`/`consents`)을 Supabase에 적용하고, domain 코드 정합을 맞춘다.

**Architecture:** 정본 설계(`db/schema.sql` 10테이블)를 영상 MVP 3테이블로 축소하고 Supabase 특화(Auth·Storage·RLS)한다. 실 DB 적용은 Supabase MCP로 수행하되 마이그레이션 실행은 사용자 승인 게이트를 거친다. Python 순수 계층(domain dataclass)은 오프라인 unittest로 검증한다.

**Tech Stack:** Supabase(PostgreSQL 15+, Auth, Storage), Supabase MCP 서버, Python 3.12 / dataclass(stdlib), unittest/pytest.

## Global Constraints

- 마이그레이션 실행·실 DB 변경은 **사용자 승인 후에만** 실행(프로젝트 규칙 §0.3 / §4.19).
- 커밋·푸시는 사용자가 명시 요청한 경우에만(§0.5).
- 모든 시각 `timestamptz`. enum 컬럼은 `text + CHECK`(D10). 비용은 `numeric`(§11-2).
- 자격증명·얼굴 URL·Base64 로그 출력 금지(§14/§15).
- 파일은 메타데이터만 저장(원본·공개 URL 금지, §4.13).
- domain dataclass 필드명 = DDL 컬럼명 = snake_case(F8 정합 게이트).
- FE는 데이터/생성/업로드를 BE 경유. FE 직접 Supabase 접근은 로그인(토큰 발급)만(§3.4).
- Provider/모델명은 env로만, 하드코딩 금지(§4.8).

---

### Task 1: Supabase MCP 인증 및 실 DB 현황 확인

**Files:**
- (없음 — MCP 도구만 사용, 코드 변경 없음)

**Interfaces:**
- Consumes: `mcp__supabase__authenticate`, `mcp__supabase__complete_authentication`, 인증 후 노출되는 `list_tables`/`execute_sql`류 도구
- Produces: 실 DB 테이블 목록(스냅샷) — Task 3의 "적용 전 상태" 근거

- [ ] **Step 1: MCP 인증 시작**

`mcp__supabase__authenticate` 호출 → 사용자에게 인증 URL 안내. 사용자가 브라우저에서 승인 후 callback URL을 받으면 `mcp__supabase__complete_authentication`로 완료.

- [ ] **Step 2: 인증 후 도구 로드**

`ToolSearch`로 `select:mcp__supabase__list_tables,mcp__supabase__execute_sql,mcp__supabase__apply_migration` 등 실제 노출된 도구 스키마 로드(도구명은 인증 후 실제 목록으로 확인 — 추정 금지).

- [ ] **Step 3: 현재 테이블 목록 조회**

`public` 스키마 테이블 목록 조회.
Expected: `generations`/`assets`/`consents` 부재(그린필드 확인). 만약 이미 존재하면 **즉시 중단**하고 사용자에게 보고(덮어쓰기 위험 — §0 되돌리기 어려운 작업).

- [ ] **Step 4: 결과 보고**

테이블 유무·기존 스키마 상태를 사용자에게 보고. 이 Task는 **읽기 전용** — 커밋/변경 없음.

---

### Task 2: MVP 마이그레이션 SQL 파일 작성 (실행 안 함)

**Files:**
- Create: `apimgr/db/migrations/0001_video_mvp.sql`

**Interfaces:**
- Consumes: 정본 `apimgr/db/schema.sql`, spec `docs/superpowers/specs/2026-07-14-video-mvp-db-schema-design.md`
- Produces: 실행 대상 마이그레이션 SQL(Task 3이 이 파일 내용을 MCP로 실행)

- [ ] **Step 1: 마이그레이션 SQL 작성**

`apimgr/db/migrations/0001_video_mvp.sql` 생성. 아래 전체 내용 그대로.

```sql
-- =============================================================================
-- 0001_video_mvp — 영상 생성 MVP 3테이블 (Supabase 적용용)
-- 정본 설계: docs/DB_SCHEMA.md / db/schema.sql (10테이블) 중 MVP 3테이블 축소본.
-- 변경점: consultation_id/customer_id nullable+FK제거, auth.users 참조 컬럼 추가.
-- 실행은 Supabase MCP로, 사용자 승인 후에만.
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
```

- [ ] **Step 2: SQL 문법 자체 점검**

파일을 다시 읽어 CHECK 목록이 `app/domain/enums.py`와 일치하는지 대조:
- `GenerationStatus`(10) ↔ generations.status CHECK
- `ProviderName`(6) ↔ generations.provider CHECK
- `GenerationType`(2) ↔ generation_type CHECK
- `CreditTxType`는 이번 테이블에 없음(consents/assets/generations 무관) — 확인만
Expected: 불일치 0.

- [ ] **Step 3: 커밋 (사용자 승인 시)**

```bash
git -C apimgr add db/migrations/0001_video_mvp.sql
git -C apimgr commit -m "feat(db): add video MVP migration SQL (assets/generations/consents)"
```
※ 커밋은 사용자가 요청한 경우에만. 아니면 파일만 남기고 스킵.

---

### Task 3: 마이그레이션 실행 (사용자 승인 게이트)

**Files:**
- (실 DB 변경 — 코드 파일 없음)

**Interfaces:**
- Consumes: `apimgr/db/migrations/0001_video_mvp.sql`, Supabase MCP 실행 도구
- Produces: 실 DB에 생성된 3테이블 + RLS 활성화 상태

- [ ] **Step 1: 사용자에게 실행 승인 요청**

마이그레이션 SQL 전문을 보여주고 "이 SQL을 실제 Supabase에 실행할까요?" 명시적 승인 요청. **승인 없이 실행 금지**(§4.19).

- [ ] **Step 2: 마이그레이션 실행**

승인 시, Supabase MCP 마이그레이션/SQL 실행 도구로 `0001_video_mvp.sql` 적용.
`auth.users` 참조 FK가 거부되면(권한/스키마 문제) 중단하고 원인 보고 — 임의 우회 금지.

- [ ] **Step 3: 적용 검증 쿼리**

다음을 조회해 결과 확인:
- 3테이블 존재: `select table_name from information_schema.tables where table_schema='public' and table_name in ('assets','generations','consents');` → 3행
- RLS 상태: `select relname, relrowsecurity from pg_class where relname in ('assets','generations','consents');` → 모두 `relrowsecurity = true`
- `generations` UNIQUE(idempotency_key)·부분 유니크 인덱스 존재 확인
Expected: 전부 통과.

- [ ] **Step 4: 결과 보고**

생성된 테이블·인덱스·RLS 상태를 사용자에게 보고. 실패 항목 있으면 명시.

---

### Task 4: Supabase Storage private bucket 생성

**Files:**
- (Supabase 설정 — 코드 파일 없음)

**Interfaces:**
- Consumes: Supabase MCP(또는 SQL) — storage 설정
- Produces: private bucket `hairview-assets`(전체 차단 RLS)

- [ ] **Step 1: 사용자 승인 요청**

private bucket 생성 계획을 알리고 승인 요청.

- [ ] **Step 2: bucket 생성**

`hairview-assets` bucket 생성(public=false). 경로 규칙: `face/{uuid}`, `video/{uuid}`.

- [ ] **Step 3: storage.objects RLS 확인**

`storage.objects`는 기본 RLS 활성. bucket 접근 정책을 별도로 만들지 않아 전체 차단 유지(BE service_role 만 접근). 상태 확인 쿼리로 정책 부재 확인.
Expected: `hairview-assets` bucket 존재, public=false, 커스텀 정책 없음.

- [ ] **Step 4: 결과 보고**

bucket 상태 보고.

---

### Task 5: domain 모델에 Asset·Consent dataclass 추가

**Files:**
- Modify: `apimgr/app/domain/models.py`
- Test: `apimgr/tests/test_models.py`

**Interfaces:**
- Consumes: `app/domain/enums.py`(기존 enum)
- Produces: `Asset`, `Consent` dataclass — 향후 Repository 구현이 사용

- [ ] **Step 1: 실패 테스트 작성**

`apimgr/tests/test_models.py` 생성.

```python
"""domain 모델 dataclass 스모크 — 필드명이 DDL 컬럼과 정합(F8)한지 최소 검증."""
import unittest
from datetime import datetime, timezone
from app.domain.models import Asset, Consent


class TestDomainModels(unittest.TestCase):
    def test_asset_minimal_construct(self):
        a = Asset(
            id="a1",
            owner_type="SALON_MEMBER",
            asset_type="FACE_SOURCE",
            storage_key="face/a1",
            mime_type="image/jpeg",
            byte_size=12345,
        )
        self.assertEqual(a.asset_type, "FACE_SOURCE")
        self.assertIsInstance(a.created_at, datetime)
        self.assertIsNone(a.expires_at)

    def test_consent_minimal_construct(self):
        c = Consent(
            id="c1",
            consent_type="EXTERNAL_AI_TRANSFER",
            granted=True,
            policy_version="v1",
        )
        self.assertTrue(c.granted)
        self.assertEqual(c.consent_type, "EXTERNAL_AI_TRANSFER")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `apimgr/.venv/Scripts/python -m unittest tests.test_models -v`
Expected: FAIL — `ImportError: cannot import name 'Asset'`

- [ ] **Step 3: dataclass 추가**

`apimgr/app/domain/models.py` 끝에 아래 추가.

```python
@dataclass
class Asset:
    """파일 메타데이터. assets 테이블 대응(원본·공개 URL 미저장, §4.13)."""

    id: str
    owner_type: str  # SALON_MEMBER / CUSTOMER / SYSTEM
    asset_type: str  # FACE_SOURCE / GENERATED_VIDEO 등
    storage_key: str
    mime_type: str
    byte_size: int
    owner_id: str | None = None          # auth.users(id)
    consultation_id: str | None = None   # MVP nullable
    width: int | None = None
    height: int | None = None
    sha256: str | None = None
    status: str = "ACTIVE"
    expires_at: datetime | None = None   # FACE_SOURCE=+24h / GENERATED_VIDEO=+7d
    deleted_at: datetime | None = None
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class Consent:
    """동의 1건. consents 테이블 대응. 없으면 CONSENT_REQUIRED(§3.9)."""

    id: str
    consent_type: str  # FACE_PROCESSING / EXTERNAL_AI_TRANSFER / STORAGE / RESULT_SHARE
    granted: bool
    policy_version: str
    account_id: str | None = None        # auth.users(id)
    consultation_id: str | None = None   # MVP nullable
    customer_id: str | None = None       # MVP nullable
    ip_hash: str | None = None
    user_agent: str | None = None
    granted_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime = field(default_factory=_utcnow)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `apimgr/.venv/Scripts/python -m unittest tests.test_models -v`
Expected: PASS (2 tests)

- [ ] **Step 5: 전체 순수계층 테스트 회귀 확인**

Run: `apimgr/.venv/Scripts/python -m unittest discover -s apimgr/tests`
Expected: 기존 테스트 + 신규 2개 전부 PASS.

- [ ] **Step 6: 커밋 (사용자 승인 시)**

```bash
git -C apimgr add app/domain/models.py tests/test_models.py
git -C apimgr commit -m "feat(domain): add Asset/Consent dataclasses for video MVP"
```

---

### Task 6: 정합·문서 마무리

**Files:**
- Modify: `apimgr/docs/DB_SCHEMA.md` (MVP 적용 상태 각주 추가)

**Interfaces:**
- Consumes: Task 3/4/5 결과
- Produces: 실 DB 상태와 문서 정합

- [ ] **Step 1: DB_SCHEMA.md에 적용 상태 반영**

`docs/DB_SCHEMA.md`에 "영상 MVP: assets/generations/consents 3테이블 Supabase 적용됨(2026-07-14), consultation_id/customer_id nullable+FK제거, auth.users 참조, RLS 전체차단" 한 단락 추가. (나머지 7테이블은 로드맵 유지 명시)

- [ ] **Step 2: 최종 보고 (§9 형식)**

변경 내용 / 이유 / 검증 결과 / 남은 위험을 §9 형식으로 보고:
- 검증: 3테이블·RLS·인덱스 조회 결과, unittest 결과
- 남은 위험: Repository 실구현 미포함(별도 단계), 만료 자동삭제 주체 미정, `auth.users` FK ON DELETE 정책 실검증 결과

- [ ] **Step 3: 커밋 (사용자 승인 시)**

```bash
git -C apimgr add docs/DB_SCHEMA.md
git -C apimgr commit -m "docs(db): note video MVP schema applied to Supabase"
```

---

## 범위 밖 (다음 계획으로 분리)

- Repository를 in-memory → Supabase 접근으로 교체(`app/repositories/`)
- 만료 자동삭제(24h/7d) 실행 주체(Worker/Supabase cron)
- 실제 Provider(PixVerse/fal/Wan) 연동, Worker 큐, FFmpeg 후처리
- Supabase Auth 연동 FE 로그인, BE 토큰 검증 미들웨어
- 로드맵 7테이블(salons/members/customers/consultations/style_*/credit_transactions)

## Self-Review 결과

- **Spec 커버리지:** spec §2(인증·소유권)→Task 2/3, §3(테이블)→Task 2/3, §4(RLS·스토리지)→Task 3/4, §5(코드영향)→Task 5, §6(적용절차)→Task 1/3/4. 누락 없음.
- **Placeholder:** 없음(모든 SQL·코드 전문 포함).
- **타입 정합:** `Asset`/`Consent` 필드명 = DDL 컬럼명 = enums 값과 일치 확인.
