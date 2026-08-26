# Hairso Studio

카테고리별 입력값과 이미지를 기반으로 세로 쇼츠 초안, Mock render, opt-in 로컬 MP4 render 흐름을 만드는 **AI 쇼츠 제작 스튜디오**(스캐폴드). Hair는 기본 카테고리 중 하나다.

> 제품 방향은 [flova.ai](https://www.flova.ai) 같은 "AI 비디오 크리에이티브 에이전트"류 서비스를 벤치마크로 하되, 소상공인 홍보 쇼츠(헤어·뷰티·로컬 비즈니스)에 특화한다. 무엇이 구현이고 무엇이 방향인지는 [`docs/LABELS.md`](./docs/LABELS.md) 기준.

## 저장소 구성

| 경로 | 역할 | 스택 | 검증 |
|---|---|---|---|
| [`hairsoui/`](./hairsoui) | FE | Next.js 15 · React 19 · TS strict · Tailwind v4 · Zod | typecheck 0 · test 20 · lint 0 |
| [`apimgr/`](./apimgr) | BE | Python 3.12 · FastAPI · Pydantic v2 | compile OK · pytest 84 · unittest 89 · TestClient 스모크 |
| [`ml/`](./ml) | 로컬 AI 추론 서비스 (opt-in) | Python · torch · diffusers · uvicorn(:8188) | GPU PC에서만 |
| [`docs/`](./docs) | 교차 문서 | — | — |

> BE 는 Python·FastAPI(루트 CLAUDE.md 규칙 우선 — 기획서의 TS BE 서술 미채택). 전체는 단일 모노레포(`hair_ai`)로 관리한다.

## 문서

- 제품/설계: [`docs/PRD.md`](./docs/PRD.md) · [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) · [`docs/PRIVACY.md`](./docs/PRIVACY.md) · [`docs/SECURITY.md`](./docs/SECURITY.md) · [`docs/PROMPT_GUIDE.md`](./docs/PROMPT_GUIDE.md) · [`docs/TEST_SCENARIOS.md`](./docs/TEST_SCENARIOS.md) · [`docs/TASKS.md`](./docs/TASKS.md)
- **산출 상태(3구간 라벨):** [`docs/LABELS.md`](./docs/LABELS.md) ← 무엇이 구현·검증완료 / Mock / 로드맵인지.
- 로컬 FE↔BE 배선 상세: [`docs/LOCAL_DEV.md`](./docs/LOCAL_DEV.md)
- 진입점: `hairsoui/CLAUDE.md` · `apimgr/CLAUDE.md`.

---

## 1. 새 PC에서 처음 실행하기

### 요구사항

| 도구 | 버전 | 확인 |
|---|---|---|
| Git | — | `git --version` |
| Python | 3.12 | `python --version` |
| Node.js | 20+ | `node -v` |

Docker Desktop이 있으면 Python·Node 없이 Docker만으로도 된다(아래 [Docker 개발 실행](#docker-개발-실행)).

### 셋업 (Windows PowerShell 기준)

```powershell
git clone https://github.com/goo-hyunju/hair_ai.git hairso
cd hairso

# 1) BE (apimgr) — 포트 8000
cd apimgr
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python main.py          # http://localhost:8000/docs
cd ..

# 2) FE (hairsoui) — 포트 3000 (다른 터미널)
cd hairsoui
npm install
npm run dev                            # http://localhost:3000 (Studio 화면은 /studio)
```

macOS/Linux는 `.venv\Scripts\` 대신 `.venv/bin/` 을 쓰면 된다.

브라우저 → FE(:3000) → `/api/*` 프록시 → BE(:8000) 구조라 FE만 열면 되고 CORS 설정이 필요 없다. 배선 상세는 [`docs/LOCAL_DEV.md`](./docs/LOCAL_DEV.md).

### AI·GPU가 없어도 전체 흐름이 돈다

기본 Provider는 전부 **Mock**이다 — API key·GPU·모델 없이 초안 생성 → render 202 → 상태 폴링 → SUCCEEDED 왕복이 실제로 동작한다(결과물은 mock 에셋). 새 PC에서는 위 셋업만 하면 된다.

실제 AI 생성은 **opt-in**이며 별도 준비가 필요하다:

| 기능 | 필요한 것 | 설정 |
|---|---|---|
| Studio 초안 텍스트 | 로컬 [Ollama](https://ollama.com) + 모델 | `DEFAULT_STUDIO_DRAFT_PROVIDER=OLLAMA` |
| 이미지 헤어 리스타일 | GPU(CUDA) + `ml/serve.py` (모델 수 GB) | `DEFAULT_IMAGE_PROVIDER=LOCAL_SD` |
| 로컬 MP4 render | GPU(CUDA) + `ml/serve.py` + 렌더 명령 | `DEFAULT_VIDEO_PROVIDER=SELF_HOSTED_WAN` |

환경변수 전체 목록은 `apimgr/.env.example`, 실행 상세는 [`docs/LOCAL_DEV.md`](./docs/LOCAL_DEV.md).
새 PC에 GPU가 없다면 이 단계를 건너뛰고 아래 **원격 AI 서버 모드**를 쓰면 된다.

---

## 2. 원격 AI 서버 모드 — 이 PC를 켜두고 다른 PC에서 쓰기

AI를 돌릴 수 없는 PC(클라이언트)에서, GPU·모델이 준비된 PC(서버)를 켜두고 빌려 쓰는 구성. 두 PC가 **같은 네트워크(공유기/사내망)** 에 있다는 전제다. 외부 접속은 아래 Tailscale 절 참조.

### 방법 A — 서버 PC에서 전부 실행, 클라이언트는 브라우저만 (가장 간단·권장)

```
[클라이언트 PC]                [서버 PC (이 PC)]
브라우저만        ──HTTP──▶  FE(0.0.0.0:3000) ─▶ BE(:8000) ─▶ ml/serve.py(:8188)
설치할 것 없음
```

서버 PC에서:

```powershell
# BE — 그대로 실행 (FE가 같은 PC에서 프록시하므로 외부 바인딩 불필요)
cd apimgr
.venv\Scripts\python main.py

# FE — 외부 접속 허용 바인딩 (다른 터미널)
cd hairsoui
npm run dev -- --hostname 0.0.0.0

# (opt-in) 로컬 AI 추론 — 같은 PC의 BE만 호출하므로 127.0.0.1 유지 (다른 터미널)
cd ml
.venv\Scripts\python -m uvicorn serve:app --host 127.0.0.1 --port 8188

# LAN IP 확인 (IPv4 주소, 예: 192.168.0.10)
ipconfig
```

방화벽은 **3000 하나만** 열면 된다 — BE(8000)·ML(8188)은 서버 내부 통신이다 (관리자 PowerShell, 최초 1회):

```powershell
netsh advfirewall firewall add rule name="hairso FE" dir=in action=allow protocol=TCP localport=3000
```

클라이언트 PC에서는 브라우저로 `http://<서버IP>:3000` 접속하면 끝. Studio 화면은 `http://<서버IP>:3000/studio`.

### 방법 B — 클라이언트에서 FE+BE 실행, AI 추론만 서버 PC 호출

클라이언트에도 개발 환경(셋업 1번)을 두고, GPU 추론(`ml/serve.py`)만 서버에서 빌리는 구성.

서버 PC에서 추론 서비스만 외부 바인딩으로 실행:

```powershell
cd ml
.venv\Scripts\python -m uvicorn serve:app --host 0.0.0.0 --port 8188

netsh advfirewall firewall add rule name="hairso ML" dir=in action=allow protocol=TCP localport=8188
```

클라이언트 PC의 `apimgr/.env`:

```text
DEFAULT_IMAGE_PROVIDER=LOCAL_SD
LOCAL_INFERENCE_URL=http://<서버IP>:8188

# 영상 render까지 서버 GPU로 돌릴 때만:
DEFAULT_VIDEO_PROVIDER=SELF_HOSTED_WAN
LOCAL_VIDEO_INFERENCE_URL=http://<서버IP>:8188
```

연결 확인: 클라이언트 브라우저에서 `http://<서버IP>:8188/health` 가 `{"status":"ok","device":"cuda"}` 를 반환하면 정상.

### 인터넷 너머(외부)에서 접속하기 — Tailscale 권장

문제는 보안이다. 이 서비스는 **고객 얼굴 이미지**를 다루고 현재 포트에 인증이 없으므로, **공유기 포트포워딩으로 3000/8188을 인터넷에 직접 여는 것은 금지**다(주소를 아는 누구나, 포트 스캔 봇까지 접근 가능).

외부 접속은 [Tailscale](https://tailscale.com)(개인 무료)로 두 PC를 가상 LAN으로 묶는 방식을 쓴다. 포트포워딩·공인 IP 불필요, 트래픽 암호화, **본인 계정 기기만 접속 가능**하다.

```powershell
# 서버 PC · 클라이언트 PC 양쪽: Tailscale 설치 후 같은 계정으로 로그인
# https://tailscale.com/download

# 서버 PC — 실행은 위와 동일 (0.0.0.0 바인딩이 Tailscale 인터페이스도 포함한다)
tailscale ip -4        # Tailscale IP 확인 (예: 100.101.102.103)

# 클라이언트 PC — 위의 <서버IP> 자리에 Tailscale IP를 쓴다
```

방화벽 규칙(위 netsh)은 동일하게 필요하다.

### 서버 PC 운영 주의

- **절전 끄기**: 설정 → 시스템 → 전원 → 화면·절전에서 "안 함". 잠자기에 들어가면 서버가 끊긴다.
- **포트를 인터넷에 직접 노출하지 말 것.** LAN 밖 접속은 반드시 Tailscale 같은 VPN 경유. 공개 노출이 필요해지면 인증부터 구현해야 한다(현재 미구현).
- `ml/serve.py` 는 단일 사용자 기준이다 — 모델을 프로세스에 1회 로드하며 동시 생성 요청이 겹치면 느려지거나 VRAM 부족이 날 수 있다.
- 생성 결과·업로드 에셋은 서버 PC 디스크(`ASSET_LOCAL_ROOT`)에 쌓인다. 고객 원본이므로 방치하지 말고 만료 정책을 따른다.

---

## Docker 개발 실행

```bash
docker compose -f docker-compose.dev.yml up --build
```

- FE: <http://localhost:3000>
- BE: <http://localhost:8000/docs>
- 기본 Provider는 Mock이며 실 외부 AI 호출, DB migration, 배포는 포함하지 않는다.
- `DEFAULT_VIDEO_PROVIDER=SELF_HOSTED_WAN` 설정 시 BE가 로컬 `/video/i2v` 호환 서버를 호출해 MP4 바이트를 `GENERATED_VIDEO` 에셋으로 저장할 수 있다. 모델 다운로드와 GPU 실행은 사용자가 별도 준비한다.

## 검증 명령

```bash
# BE
cd apimgr && .venv/Scripts/python -m pytest -q
# FE
cd hairsoui && npm run typecheck && npm run test && npm run build
```

## 핵심 특성

- 카테고리 기반 Promotion Short. Hair, Beauty, Health, Product, Local Business를 같은 Studio 흐름에서 다룬다.
- 외부 AI 는 BE 경유(FE 직접 호출 금지). 비동기 202+job_id. Idempotency·상태 전이 단일 관리. 기본 Mock Provider.
- 하이브리드 반응형(웹+모바일 한 코드베이스, 네이티브 아님).

## 주의

실 외부 AI·실 DB·카메라 실동작 등은 **로드맵**(미구현). 상세·미검증 외부 사실은 [`docs/LABELS.md`](./docs/LABELS.md) 참조.
