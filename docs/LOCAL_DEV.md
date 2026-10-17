# 로컬 개발 실행 — FE ↔ BE 통합 배선 (검증본)

hairso 를 로컬에서 BE(apimgr) + FE(hairsoui) 함께 띄우는 단일 안내다.
아래 배선은 **실제 왕복(202 → 상태폴링 → SUCCEEDED)까지 실행해 검증**했다(2026-10-17 Mock Provider 왕복 재검증).

## 포트·경로 계약 (고정값)

| 항목 | 값 | 근거 |
| --- | --- | --- |
| BE(apimgr) 포트 | **8000** | `hairsoui/next.config.mjs` 프록시 대상이 `http://127.0.0.1:8000` (uvicorn 기본) |
| FE(hairsoui) 포트 | **3000** | `next dev` 기본 |
| BE API prefix | `/api/v1/*` | 라우터 prefix (`app/api/v1/generations.py` 등) |
| FE 요청 경로 | `/api/v1/*` | `src/lib/api/generations.ts` — BE 와 동일 |

## 브라우저 → BE 연결 방식: **Next 프록시 (CORS 미사용)**

```
브라우저 → FE(:3000) /api/*  ──[next.config rewrites]──▶  BE(:8000) /api/*
```

- `next.config.mjs` 의 `rewrites()` 가 `/api/:path*` 를 `http://127.0.0.1:8000/api/:path*` 로 서버사이드 전달한다.
- 브라우저 입장에선 **same-origin(:3000)** 이므로 **CORS 설정이 필요 없다.** BE 에 CORS 미들웨어를 두지 않는 것은 의도된 설계다.
- 프록시 대상 포트는 `API_PROXY_TARGET` env 로 바꿀 수 있다(기본 `http://127.0.0.1:8000`).
- **운영(production)은 이 프록시가 아니라 실제 게이트웨이/도메인**을 쓴다. 그때 FE 가 BE 를 다른 오리진으로 직접 호출한다면 그 시점에 BE CORS 또는 동일 도메인 라우팅을 도입한다(로드맵).

## 환경변수 (dev 기준)

- **FE `NEXT_PUBLIC_API_BASE_URL` = 빈 값**(미설정). 프록시를 쓰므로 `client.ts` 의 `BASE_URL ?? ""` 로 same-origin `/api/*` 를 호출한다. 별도 `.env.local` 없이 동작한다.
- BE Provider 키 미설정 → 전부 **Mock**. 유료 외부 호출·키 없이 전체 흐름 동작(§0.16).

## 실행 순서

```bash
# 1) BE (apimgr) — 포트 8000
cd apimgr
python -m venv .venv                                   # 최초 1회
.venv/Scripts/python -m pip install -e ".[dev]"        # 최초 1회
.venv/Scripts/python main.py                           # 진입점 main.run() — 포트 8000, reload 켜짐
# (동등한 명시 실행) .venv/Scripts/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 2) FE (hairsoui) — 포트 3000 (다른 터미널)
cd hairsoui
npm install                                            # 최초 1회
npm run dev
```

브라우저에서 <http://localhost:3000> 접속. FE 의 API 호출은 자동으로 `/api/*` → BE 로 프록시된다.
Studio 작업 화면은 <http://localhost:3000/studio> 이다.

## Docker Compose 개발 실행

Docker가 설치된 환경에서는 루트에서 FE+BE를 한 번에 띄울 수 있다. 이 compose는 **개발 전용**이며 실 DB, migration, 유료 Provider, GPU/ML 서비스를 포함하지 않는다.

```bash
docker compose -f docker-compose.dev.yml up --build
```

서비스:

| 서비스 | 내부 포트 | 호스트 포트 | 역할 |
| --- | --- | --- | --- |
| `apimgr` | 8000 | 127.0.0.1:8000 | FastAPI, Mock Provider, local asset volume |
| `hairsoui` | 3000 | 3000 | Next dev server, `/api/*` -> `http://apimgr:8000/api/*` 프록시 |

`hairsoui`는 `apimgr` healthcheck가 통과한 뒤 시작한다. healthcheck는 컨테이너 내부에서 `GET /health`를 확인한다.

Compose 환경변수:

- BE `APP_HOST=0.0.0.0`, `LOCAL_VIDEO_TIMEOUT_SECONDS=900`, `MOCK_ADVANCE_INTERVAL_SEC=1.0`
- FE `API_PROXY_TARGET=http://apimgr:8000`
- FE `NEXT_PUBLIC_API_BASE_URL=` 빈 값 유지
- BE `DEFAULT_*_PROVIDER=MOCK`
- BE `DEFAULT_STUDIO_DRAFT_PROVIDER=MOCK`
- BE `LOCAL_VIDEO_INFERENCE_URL=http://host.docker.internal:8188` (기본 Mock이라 호출하지 않음)
- BE `ASSET_STORE_BACKEND=LOCAL_DISK`
- BE `ASSET_LOCAL_ROOT=/var/lib/hairso/assets`
- BE `STUDIO_STORAGE_PROFILE_NAME=local-dev`
- BE `STUDIO_OUTPUT_PREFIX=studio/outputs`
- BE `STUDIO_OUTPUT_RETENTION_DAYS=30`

Studio 초안 자동생성에 로컬 Ollama를 쓰려면 BE 환경에만 다음을 설정한다. FE는 Ollama를 직접 호출하지 않는다.

```text
DEFAULT_STUDIO_DRAFT_PROVIDER=OLLAMA
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_STUDIO_DRAFT_MODEL=<local-model-name>
OLLAMA_TIMEOUT_SECONDS=60
```

Ollama가 꺼져 있거나 모델명이 없으면 Studio draft는 기존 Mock 초안으로 동작한다.

Studio render를 로컬 MP4 provider로 시험하려면 BE 환경에만 다음을 설정한다. 이 경로도 FE가 provider를 직접 호출하지 않는다.

```text
DEFAULT_VIDEO_PROVIDER=SELF_HOSTED_WAN
LOCAL_VIDEO_INFERENCE_URL=http://127.0.0.1:8188
LOCAL_VIDEO_ENDPOINT_PATH=/video/i2v
LOCAL_VIDEO_TIMEOUT_SECONDS=3600
SELF_HOSTED_WAN_VIDEO_MODEL=<local-wan-or-compatible-model-name>
VIDEO_GENERATION_POLL_INTERVAL_SECONDS=10
# 비우면 LOCAL_VIDEO_TIMEOUT_SECONDS 기준으로 자동 계산
VIDEO_GENERATION_MAX_POLLS=
```

`ml/serve.py`는 영상 job API를 제공한다. `POST /video/i2v`는 오래 막히지 않고 `job_id`를 즉시 반환하고, BE는 `GET /video/i2v/{job_id}`를 polling하다가 `GET /video/i2v/{job_id}/output`에서 MP4를 받아 Storage에 저장한다.

Studio render 는 프로젝트 duration(5/15/30초)·9:16·480p 를 전달한다. ml 의 내장 Diffusers 경로는 `WAN_VIDEO_MAX_SECONDS`(기본 5)로 요청 초를 자른 뒤 프레임 올림으로 인코딩하고(기본 약 5.04초), `LOCAL_VIDEO_RENDER_COMMAND` 외부 명령 경로는 요청 길이를 그대로 전달한다. 720p는 API에서 허용하지만 8GB VRAM 환경에서는 스모크 테스트 후 켠다. 기본은 프로세스 내 Wan Diffusers 경로다. 실제 설치·모델 다운로드는 대용량 작업이므로 명시 승인 후 진행한다.

```bash
cd ml
.venv/Scripts/python -m pip install -r requirements-wan.txt
$env:WAN_VIDEO_MODEL_ID='Wan-AI/Wan2.2-TI2V-5B-Diffusers'
$env:WAN_VIDEO_MAX_SECONDS='5'
$env:WAN_VIDEO_FPS='24'
.venv/Scripts/python -m uvicorn serve:app --host 127.0.0.1 --port 8188
```

GGUF transformer를 쓰는 경우에는 Diffusers GGUF 경로가 실제 파일과 호환되는지 스모크 테스트로 확정해야 한다. 값은 환경변수로만 지정한다.

```bash
$env:WAN_VIDEO_TRANSFORMER_GGUF='C:\path\to\wan2.2-ti2v-5b-q5_k_m.gguf'
```

기존 외부 렌더 스크립트를 유지하려면 `ml/serve.py`를 실행하는 터미널에 로컬 렌더 명령을 지정한다. 명령은 `{input}`, `{prompt_file}`, `{output}`, `{meta_file}` placeholder를 사용할 수 있다.

```bash
cd ml
# serve.py 가 subprocess 를 임시 작업 디렉터리에서 실행하므로 Python 과 스크립트는 절대 경로로 지정한다
$env:LOCAL_VIDEO_RENDER_COMMAND='C:\path\to\ml\.venv\Scripts\python.exe C:\path\to\your_render_script.py --image {input} --prompt-file {prompt_file} --output {output}'
$env:LOCAL_VIDEO_RENDER_TIMEOUT_SECONDS='3600'
.venv/Scripts/python -m uvicorn serve:app --host 127.0.0.1 --port 8188
```

`LOCAL_VIDEO_RENDER_COMMAND`가 없으면 `ml/wan_video.py` 가 `Wan-AI/Wan2.2-TI2V-5B-Diffusers`를 로드한다(기본 경로). 저장소에 모델 파일은 포함하지 않으며, 최초 로드 시 Hugging Face Hub 에서 자동 다운로드한다(약 32GB — 작성자 보고, 자동 검증 없음).

Compose volume:

- `hairso_asset_data`: 고객 이미지/결과 mock asset 저장 위치. 컨테이너 내부 repo 밖 `/var/lib/hairso/assets`에 마운트한다.
- `hairsoui_node_modules`: Linux 컨테이너용 `node_modules`를 host 소스 mount와 분리한다.
- `hairsoui_next`: Next dev 산출물 `.next`를 host bind mount와 분리한다.

## LAN AI 서버 PC 모드

이 PC를 미용실 내부 AI 서버처럼 두고 다른 PC·태블릿·외부 프로그램이 붙는 경우에도 기본 원칙은 같다.

```text
외부 브라우저/프로그램
→ Hairso FE 또는 apimgr API
→ apimgr
→ local Ollama / local image provider / SELF_HOSTED_WAN
```

기본 권장 모드:

- 브라우저 사용자는 `http://<server-ip>:3000`만 접속한다.
- Docker compose 기본값은 `hairsoui:3000`만 LAN에 열고, `apimgr:8000`은 `127.0.0.1`에만 묶는다.
- `ml:8188`, `Ollama:11434`는 외부 PC에 직접 공개하지 않는다.
- Provider key, storage key, signed URL, Base64 이미지, 고객 얼굴 URL은 FE·외부 프로그램·로그에 노출하지 않는다.

외부 프로그램이 BE API를 직접 호출해야 할 때:

- `APP_HOST=0.0.0.0` 또는 서버 NIC IP bind는 인증·방화벽 정책을 정한 뒤에만 사용한다.
- Windows Firewall에서 허용 클라이언트 IP 또는 VPN 대역을 제한한다.
- 브라우저 기반 외부 앱이면 CORS `allow_origins`를 `*`가 아니라 명시 allowlist로 둔다.
- 현재 인증은 선택적이므로 실 고객 이미지·실 Provider 작업 전에 인증 필수화와 DB 기반 idempotency가 필요하다.

공개 인터넷 노출은 이 개발 compose 범위가 아니다. TLS, reverse proxy, rate limit, 감사 로그, 지속 저장소, 공유 토큰 만료 정책이 먼저 확정되어야 한다.

## Tailscale 모바일 접속

이 PC와 핸드폰이 같은 Tailnet에 있으면 FE만 Tailscale IP로 열어 모바일에서 접속한다. BE와 ML은 서버 PC 내부 주소를 유지한다.

```bash
# BE
cd apimgr
$env:APP_LOAD_DOTENV='0'
$env:ASSET_STORE_BACKEND='LOCAL_DISK'
$env:DEFAULT_VIDEO_PROVIDER='SELF_HOSTED_WAN'
$env:LOCAL_VIDEO_INFERENCE_URL='http://127.0.0.1:8188'
$env:LOCAL_VIDEO_ENDPOINT_PATH='/video/i2v'
$env:LOCAL_VIDEO_TIMEOUT_SECONDS='3600'
$env:SELF_HOSTED_WAN_VIDEO_MODEL='Wan-AI/Wan2.2-TI2V-5B-Diffusers'
$env:VIDEO_GENERATION_POLL_INTERVAL_SECONDS='10'
.venv/Scripts/python -m uvicorn main:app --host 127.0.0.1 --port 8010

# ML
cd ml
$env:WAN_VIDEO_MODEL_ID='Wan-AI/Wan2.2-TI2V-5B-Diffusers'
$env:WAN_VIDEO_MAX_SECONDS='5'
$env:WAN_VIDEO_FPS='24'
$env:WAN_VIDEO_NUM_INFERENCE_STEPS='20'
$env:WAN_VIDEO_OFFLOAD='group'
.venv/Scripts/python -m uvicorn serve:app --host 127.0.0.1 --port 8188

# FE: 외부 기기 접속 허용
cd hairsoui
$env:API_PROXY_TARGET='http://127.0.0.1:8010'
npm run dev -- --hostname 0.0.0.0 --port 3001
```

핸드폰 브라우저:

```text
http://<이-PC의-Tailscale-IP>:3001/studio
```

예를 들어 서버 PC 의 Tailscale IP 가 `100.x.y.z` 이면:

```text
http://100.x.y.z:3001/studio
```

Windows Firewall은 TCP 3001만 Tailnet 클라이언트에서 접근 가능하게 연다. `8000`, `8188`, `11434`는 외부 직접 접근 대상으로 두지 않는다.

Compose smoke:

```bash
curl -s http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:3000/api/v1/video-generations \
  -H "Content-Type: application/json" \
  -d '{"consultation_id":"c-1","image_asset_id":"a-1","prompt":"jaw length bob","duration_seconds":5,"aspect_ratio":"9:16","quality":"720p","idempotency_key":"docker-smoke-1"}'
```

중지:

```bash
docker compose -f docker-compose.dev.yml down
```

asset volume까지 지우는 명령은 저장 데이터를 삭제하므로 필요할 때만 별도 판단한다.

## 왕복 스모크 (프록시 경유, 검증됨)

```bash
# 202 + generation_id
curl -s -X POST http://127.0.0.1:3000/api/v1/video-generations \
  -H "Content-Type: application/json" \
  -d '{"consultation_id":"c-1","image_asset_id":"a-1","prompt":"jaw length bob","duration_seconds":5,"aspect_ratio":"9:16","quality":"720p","idempotency_key":"idem-1"}'

# 상태 조회 (SUBMITTED → PROCESSING → SUCCEEDED)
curl -s http://127.0.0.1:3000/api/v1/generations/<generation_id>
```

검증 결과(Mock): `POST → 202 SUBMITTED`, 폴링 `PROCESSING → SUCCEEDED`, 같은 `idempotency_key` 재요청 시 **동일 generation_id** 반환.

## Studio smoke (Mock)

```bash
# 1) Studio project 생성
curl -s -X POST http://127.0.0.1:3000/api/v1/studio/projects \
  -H "Content-Type: application/json" \
  -d '{"template_type":"PROMOTION_SHORT","category":"HAIR","title":"봄맞이 클리닉 이벤트","offer_text":"첫 방문 20% 할인","cta_text":"오늘 예약 문의하기","duration_seconds":15,"tone":"FRIENDLY","asset_ids":[]}'

# 2) 초안 생성(MOCK 기본, OLLAMA 로컬 옵션)
curl -s -X POST http://127.0.0.1:3000/api/v1/studio/projects/<project_id>/draft

# 3) render 시작(MOCK 기본, SELF_HOSTED_WAN opt-in 가능)
curl -s -X POST http://127.0.0.1:3000/api/v1/studio/projects/<project_id>/render \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key":"studio-smoke-1"}'

# 4) 기존 generation polling 재사용
curl -s http://127.0.0.1:3000/api/v1/generations/<generation_id>
```

Studio 응답은 `output_asset_id` 같은 내부 참조만 반환하고, signed URL·storage key·provider raw payload는 반환하지 않는다.

## 주의 (알려진 경계)

- `/health` 는 `/api` prefix 밖(`GET /health`)이라 **프록시(/api/*)로는 닿지 않는다.** 헬스체크는 BE 에 직접(`http://127.0.0.1:8000/health`). FE 는 health 를 호출하지 않으므로 문제 없음.
- 인메모리 저장소는 **단일 프로세스·재시작 시 초기화**(스캐폴드). 실 DB(Supabase) 저장소는 `DATABASE_URL` 설정 시 활성(로드맵 정합 진행 중).
- Mock 상태 전진은 데모용 `BackgroundTask` 다. 실 Worker 큐는 로드맵(§4.9).
- Docker compose도 Mock 개발 경로다. `.env`, Provider key, Supabase secret, 고객 원본 URL을 이미지·로그·문서에 넣지 않는다.
