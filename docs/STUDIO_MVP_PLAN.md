# Hairso Studio MVP Plan

이 문서는 현재 Mock 생성 스캐폴드 다음에 구현할 Studio 제품 범위를 고정한다. 목표는 완전한 범용 편집기가 아니라, 카테고리별 입력값을 받아 세로 쇼츠 제작 흐름 하나를 안정적으로 완성하는 것이다. Hair는 첫 기본 카테고리 중 하나이며 제품 전체의 유일한 중심이 아니다.

현재 구현 상태:

- BE `/api/v1/studio/projects` project/draft/render Mock 흐름 추가.
- FE `/studio` 작업 화면에 `Templates -> Draft -> Render -> Result` 단계형 흐름 추가.
- DB 확장 DDL 초안 `apimgr/db/migrations/0003_studio_mvp.sql` 추가. 실행은 사용자 승인 대상.
- 저장 위치 설정은 `ASSET_STORE_BACKEND`, `ASSET_LOCAL_ROOT`, `SUPABASE_STORAGE_BUCKET`, `STUDIO_STORAGE_PROFILE_NAME`, `STUDIO_OUTPUT_PREFIX`, `STUDIO_OUTPUT_RETENTION_DAYS`로 분리.
- 템플릿은 `PROMOTION_SHORT`, `SALON_EVENT_PROMOTION`, 카테고리는 `HAIR`, `BEAUTY`, `HEALTH`, `PRODUCT`, `LOCAL_BUSINESS`로 분리.
- Studio 입력의 `asset_ids`와 `logo_asset_id`는 URL, 경로, Base64 형태를 거부하고 기존 asset 메타데이터의 존재·상태·소유자·타입을 확인한다.
- Studio 초안 생성은 `StudioDraftProvider`로 분리. 기본은 결정적 `MOCK`, 옵션으로 로컬 `OLLAMA`를 사용할 수 있다.
- Project/draft 텍스트 필드는 URL, signed URL, storage key, Base64 형태를 거부해 초안 provider prompt 로 민감 media 참조가 들어가지 않게 한다.
- Studio render는 `DEFAULT_VIDEO_PROVIDER=MOCK` 기본 경로를 유지한다. `SELF_HOSTED_WAN`으로 명시 설정하면 BE가 로컬 영상 추론 서버(`/video/i2v`)를 호출해 반환된 MP4 바이트를 `GENERATED_VIDEO` 에셋으로 저장할 수 있다.
- 로컬 영상 provider는 모델 다운로드나 유료 API를 수행하지 않는다. 실제 Wan/CogVideoX/ComfyUI 실행은 `ml/serve.py`의 `LOCAL_VIDEO_RENDER_COMMAND`로 사용자가 별도 설정한 로컬 명령이 담당한다.

## 1. 첫 템플릿 결정

첫 happy path 템플릿은 **Promotion Short**로 한다. 함께 노출하는 두 번째 템플릿은 **Event Promotion**이며, 기본 카테고리는 **Hair**지만 같은 구조로 Beauty, Health, Product, Local Business까지 확장한다.

이유:

- 고객 얼굴 원본 없이도 홍보 문구, 제품/매장/시술 이미지, 로고만으로 Mock end-to-end를 검증할 수 있다.
- 현재 남아 있는 얼굴 asset 소유권·동의 부채에 덜 민감하다.
- 운영자가 가격, 기간, 혜택, 예약 CTA를 입력하는 흐름이 명확하다.
- Before/After와 Hair Simulation은 고객 얼굴, 결과 보장 안내, 동의 정책이 먼저 단단해야 한다.

## 2. MVP 사용자 흐름

```text
Templates
-> 이벤트/프로모션 정보 입력
-> 이미지·로고 업로드 또는 asset_id 선택
-> Draft: script/storyboard 초안 생성(MOCK 기본, OLLAMA 로컬 옵션)
-> 사용자가 문구와 장면을 편집
-> Render: Mock render job 또는 opt-in SELF_HOSTED_WAN 로컬 MP4 job 시작
-> 기존 generation 상태 조회로 polling
-> Result: output_asset_id 참조, preview/download/QR placeholder 또는 로컬 MP4 asset 표시
```

`/try` 저수준 생성 데모는 제품 진입점에서 제외한다. 필요하면 내부 회귀 확인용 route로만 남긴다. Studio는 별도 흐름으로 추가하고, 기존 `POST /api/v1/video-generations`와 `GET /api/v1/generations/{id}`를 재사용한다.

## 3. 입력 범위

필수 입력:

- `template_type`: `PROMOTION_SHORT` 또는 `SALON_EVENT_PROMOTION`
- `category`: `HAIR`, `BEAUTY`, `HEALTH`, `PRODUCT`, `LOCAL_BUSINESS`
- `title`: 이벤트명 또는 시술명
- `offer_text`: 가격, 할인, 기간, 조건
- `cta_text`: 예약, 상담, 전화, 카카오 문의 같은 행동 유도 문구
- `duration_seconds`: `15` 또는 `30`

선택 입력:

- `target_audience`: 예: 신규 고객, 기존 고객, 염색 관심 고객
- `tone`: `CALM`, `TRENDY`, `PREMIUM`, `FRIENDLY`
- `asset_ids`: 최대 6개. URL, 경로, Base64 문자열은 거부하고 asset 메타데이터를 확인
- `logo_asset_id`: 최대 1개. `asset_ids`와 같은 검증 적용
- `disclaimer`: 매장 정책 또는 가격 조건 안내

## 4. 초안 데이터 구조

초안은 `studioDraftSchema` 구조로 생성한다. 기본 `MOCK` 초안은 결정적으로 생성한다. 같은 입력이면 같은 구조가 나와야 테스트가 쉽다. `DEFAULT_STUDIO_DRAFT_PROVIDER=OLLAMA`를 설정하면 BE가 로컬 Ollama 서버에 텍스트 초안 생성을 요청할 수 있다. Ollama가 실패하거나 설정이 부족하면 기존 Mock 초안으로 fallback한다.

작성 규칙:

- 자막·나레이션·CTA는 한국어로 작성한다.
- `visual_prompt`는 영상 모델이 이해하기 쉬운 영어 image-to-video 모션 지시로 작성한다.
- 고객 이미지 URL, signed URL, storage key, Base64는 초안 provider prompt와 응답에 포함하지 않는다.
- provider가 반환한 draft도 저장 전 같은 민감 문자열 검증을 통과해야 하며, render 직전 저장 draft를 다시 검증한다.
- 15초는 3개 장면, 30초는 provider clip 한도에 맞춘 5개 장면(예: `5+6+6+8+5`)으로 나눈다.
- `HEALTH` 카테고리는 사용자 제공/승인 자료 없이 진단·치료·복용량 같은 의료 주장을 만들지 않는다.

```json
{
  "project_id": "uuid",
  "template_type": "PROMOTION_SHORT",
  "category": "HAIR",
  "title": "봄맞이 클리닉 이벤트",
  "script": {
    "hook": "이번 주, 푸석한 머릿결을 차분하게 정리해 보세요.",
    "narration": [
      "손상 모발을 위한 집중 클리닉 이벤트를 준비했습니다.",
      "상담 후 모발 상태에 맞춰 케어 단계를 추천해 드립니다.",
      "예약 문의는 프로필 링크 또는 매장 전화로 남겨 주세요."
    ],
    "cta": "오늘 예약 문의하기"
  },
  "storyboard": [
    {
      "scene_index": 1,
      "duration_seconds": 5,
      "caption": "봄맞이 클리닉 이벤트",
      "visual_prompt": "Photorealistic salon treatment close-up, slow camera push-in, natural movement, 9:16"
    }
  ]
}
```

초안은 사용자가 편집한 뒤 저장되어야 한다. 생성 요청은 저장된 편집본을 기준으로 시작한다.

## 5. API 방향

첫 구현은 DB migration 없이 in-memory/mock으로 시작한다.

후보 API:

- `POST /api/v1/studio/projects`: 프로젝트 생성
- `POST /api/v1/studio/projects/{project_id}/draft`: script/storyboard 초안 생성(MOCK 기본, OLLAMA 로컬 옵션)
- `PATCH /api/v1/studio/projects/{project_id}/draft`: 편집본 저장
- `POST /api/v1/studio/projects/{project_id}/render`: 기존 generation job 생성
- `GET /api/v1/studio/projects/{project_id}`: 프로젝트와 render 상태 조회

응답에는 signed URL, 원본 storage key, provider raw payload를 넣지 않는다. 결과 참조는 `output_asset_id` 같은 내부 ID만 사용한다. Mock render는 작은 MP4 컨테이너 fixture를 저장해 asset 참조를 검증한다. `SELF_HOSTED_WAN` opt-in 경로는 로컬 추론 서버가 반환한 실제 MP4 바이트만 저장하며, URL 문자열만 있는 provider 결과는 성공으로 처리하지 않는다.

이미지 없이 시작하는 Mock render는 내부 `VideoGenerationInput.image_asset_id`와 `generations.input_asset_id`를 `null`로 둘 수 있다. `SELF_HOSTED_WAN`은 source asset이 있으면 BE 내부에서만 바이트를 읽어 multipart로 로컬 서버에 전달하고, asset URL·storage key·Base64는 전달하지 않는다. 운영 DB에서 FK가 강해지면 실제 placeholder/source asset 레코드를 만든 뒤 연결해야 한다.

## 6. FE 화면 방향

첫 화면은 랜딩이 아니라 작업 화면이다.

- 모바일: 단계형 단일 컬럼
- 태블릿/데스크톱: 입력/초안 편집 영역과 9:16 preview 영역을 나란히 배치
- 스크립트와 storyboard는 생성 전 편집 가능
- 실패 메시지는 기존 `errorMessageView`를 사용
- 고객 얼굴 원본이나 결과 URL은 browser storage에 저장하지 않음

## 7. 완료 기준

- `/try`는 제품 진입점에서 제거하고, 필요 시 내부 회귀 데모로만 유지
- Studio `Templates -> Draft -> Render -> Result` 흐름이 Mock으로 끝까지 진행
- `DEFAULT_VIDEO_PROVIDER=SELF_HOSTED_WAN` opt-in 시 로컬 `/video/i2v` 호환 서버가 반환한 MP4 바이트를 `GENERATED_VIDEO`로 저장
- `PROMOTION_SHORT`와 `SALON_EVENT_PROMOTION`이 모두 draft 생성 경로를 통과
- 생성 전 script/storyboard가 보이고 편집 가능
- 같은 프로젝트에서 반복 클릭해도 중복 render job을 만들지 않음
- Studio asset 참조는 위험한 문자열과 존재하지 않는 asset을 거부
- 소유자 없는 `GENERATED_IMAGE`는 Studio 입력으로 참조할 수 없음
- project/draft 텍스트의 URL·Base64·storage key 형태는 거부
- 실제 Provider, DB migration, FFmpeg, R2 없이 로컬 검증 가능
- FE는 외부 AI Provider를 직접 호출하지 않음
- BE 로그와 응답에 secret, signed URL, Base64, 원본 이미지 URL 미노출
- `OLLAMA` draft provider를 켜도 호출은 BE 내부에서만 발생하고, 실패 시 Mock 초안으로 fallback

## 8. 이번 Docker 패치 범위

Docker는 제품 기능이 아니라 로컬 재현성을 위한 개발 도구로 둔다.

포함:

- `docker-compose.dev.yml`
- `apimgr/Dockerfile.dev`
- `hairsoui/Dockerfile.dev`
- 루트 `.dockerignore`
- `docs/LOCAL_DEV.md` 실행 안내 보강
- BE asset named volume은 컨테이너 내부 `/var/lib/hairso/assets`에만 마운트

제외:

- PostgreSQL 컨테이너와 migration 실행
- Supabase/R2 실 연결
- PixVerse, Gemini, fal, Wan Cloud 실제 호출
- 대용량 Wan/CogVideoX 모델 다운로드와 GPU 추론 실행
- GPU/ML 컨테이너
- production Dockerfile 또는 배포 설정

## 9. 다음 구현 순서

1. `/studio` 단계형 flow의 result placeholder를 실제 MP4 preview로 교체한다.
2. `SELF_HOSTED_WAN` 로컬 서버에 Wan/CogVideoX/ComfyUI 명령을 연결해 샘플 MP4 생성 시간을 측정한다.
3. 업로드/선택 UI를 asset_id 직접 입력 대신 파일·라이브러리 선택으로 교체한다.
4. QR/share token은 만료·권한 정책 확정 뒤 추가한다.
5. DB persistence와 Worker queue는 migration 승인 뒤 도입한다.
6. Wan 2.2 같은 실제 scene video provider는 로컬 GPU/비용/라이선스 검토 뒤 운영 provider로 승격한다.
7. credits, cost history는 별도 승인 뒤 도입한다.
