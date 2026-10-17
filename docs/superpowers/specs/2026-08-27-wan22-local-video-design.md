# Wan 2.2 TI2V-5B 로컬 영상 생성 통합 — 설계 스펙

날짜: 2026-08-27
상태: 구현 반영됨(`ml/wan_video.py`, `ml/serve.py`) — 구현과 상이한 항목: 결과는 `GET /video/i2v/{job_id}/output` 로 분리, provider `_outputs` 유지, env 명은 `VIDEO_GENERATION_POLL_INTERVAL_SECONDS`/`VIDEO_GENERATION_MAX_POLLS`, 완료 job TTL 미구현, GGUF 는 opt-in(기본 bf16 Diffusers), 네트워크 오류는 즉시 FAILED(재시도·순단 흡수 없음), 1080p→480p·1:1→9:16 강등에 클램프 메타 없음, 초기 상태 PENDING, 기본 group offload. RAM 32GB 는 작성자 권장값(64GB 환경 실측)
관련: `docs/PRD-video-studio.md`, 프로젝트 규칙 §4.9/§4.16/§6.1(비공개)

## 1. 목표와 결정 사항

무료(완전 로컬, 외부 API 0원)로 최고 품질의 영상 생성을 hairso에 적용한다.

확정된 결정(사용자 승인):

| 결정 | 선택 | 근거 |
|---|---|---|
| 무료 방식 | 로컬 GPU 자체 호스팅 | 횟수 무제한, 고객 얼굴 외부 전송 없음. 외부 사용자는 VPN으로 이 서버에 접속 |
| 모델 | Wan 2.2 TI2V-5B (Apache 2.0) | 8GB VRAM에서 실행 가능한 오픈소스 중 인물·얼굴 품질 최상. §6.1 얼굴 유지 요구와 부합 |
| 실행 방식 | diffusers 직접 통합 (ml/serve.py 내장) | 기존 SD1.5 restyle 과 동일 스택·패턴. ComfyUI 의존성 배제 |
| 품질 우선 | Q5_K_M 양자화, 증류 LoRA 미적용 | 사용자 확정: "영상 퀄리티가 중요" — 공격적 경량화 배제 |
| T2V 지원 | 포함 | 사용자 요청(예: 춤추는 고양이). TI2V-5B 는 텍스트 전용 생성도 지원 |

## 2. 환경 (실측 확인)

- GPU: RTX 5060 Ti **8GB** (nvidia-smi 실측 8151MiB)
- RAM 64GB, 디스크 C 여유 221GB
- ml venv: torch 2.11.0+cu128, diffusers 0.39.0, transformers 5.13.1, accelerate 1.14.0
- diffusers 0.39.0 소스 확인: `WanImageToVideoPipeline`(+`expand_timesteps` TI2V-5B 모드), `GGUFQuantizationConfig`, `WanTransformer3DModel.from_single_file`, `export_to_video` 모두 존재
- **미설치(추가 필요)**: `imageio` + `imageio-ffmpeg`(MP4 인코딩), `gguf`(GGUF 로딩)

## 3. 아키텍처

```
FE → BE(apimgr :8000, DEFAULT_VIDEO_PROVIDER=SELF_HOSTED_WAN)
   → ml/serve.py(:8188, 127.0.0.1 바인딩 유지)
       POST /video/i2v          → 즉시 {job_id}     (job 등록)
       GET  /video/i2v/{job_id} → 상태 JSON | MP4    (폴링)
   → BE GenerationWorker 가 MP4 를 AssetStore 저장 → FE 폴링/다운로드
```

외부 접속: VPN → FE/BE. ml 서버는 외부 직접 노출 없음(기존 `_LOCAL_HOSTS` 제약 유지).

### 3.1 검증에서 확인된 BE 갭과 해결 (이 설계의 핵심 변경)

- **갭 ①**: 현 구조는 `provider.submit()` 이 라우터 요청 안에서 MP4 완성까지 대기 → POST 가 5~20분 블로킹, 프록시/브라우저 타임아웃, §3.8 새로고침 복원 불가.
  → **해결**: ml 서버를 job 방식(위 계약)으로 변경. `SelfHostedWanVideoProvider.submit` 은 job 등록만 하고 즉시 반환, `get_status` 는 ml 서버 GET 을 폴링. `VideoProvider` 추상 계약(submit→external_job_id, get_status→폴링)에 정합.
- **갭 ②**: BE 데모 폴링 루프가 8회×1초로 종료 → 수 분짜리 실생성을 못 기다림.
  → **해결**: 루프 간격·최대 횟수를 env 로 확장(예: `VIDEO_POLL_INTERVAL_SEC` 기본 10초, `VIDEO_POLL_MAX_ATTEMPTS` 기본 240 = 최대 40분).
- 기각된 지적: "provider 인스턴스 비싱글톤으로 submit/폴링 `_outputs` 어긋남" — 동일 인스턴스가 BackgroundTask 로 전달됨(`generations.py:85→122`)이라 단일 프로세스에서는 문제없음. 멀티 워커 배포 시에만 유효(로드맵). job 방식 전환 후에는 상태가 ml 서버에 있으므로 이 문제 자체가 소멸.

## 4. ml 서버 상세

### 4.1 신규 `ml/wan_video.py`

- `WanVideoGenerator`: 최초 요청 시 1회 로드(기존 `HairRestyler` 패턴).
- 로딩 구성:
  - transformer: QuantStack `Wan2.2-TI2V-5B-GGUF` **Q5_K_M**(3.81GB) → `WanTransformer3DModel.from_single_file` + `GGUFQuantizationConfig(compute_dtype=bfloat16)`
  - 나머지 컴포넌트(text_encoder umt5-xxl, VAE, scheduler, tokenizer): `Wan-AI/Wan2.2-TI2V-5B-Diffusers`
  - `enable_model_cpu_offload()` + VAE 타일링 → 8GB VRAM 대응(RAM 64GB 활용)
  - 텍스트 인코더 양자화본(umt5-xxl GGUF)은 스모크에서 품질 무영향 확인 시에만 채택(다운로드 34GB→약 10GB)
- `generate(image|None, prompt, negative_prompt, duration_seconds, aspect_ratio, quality, seed) -> mp4 bytes`
  - image 있음 → `WanImageToVideoPipeline`(I2V), 없음 → T2V 경로. 컴포넌트 공유(추가 메모리 없음)
  - 24fps, 5초=121프레임. **클램프**: duration 8→5초, quality 1080p→720p(모델 상한). 클램프 발생은 응답 메타로 알리되 오류로 처리하지 않음
  - 해상도 매핑(quality×aspect_ratio): 480p → 480×832(9:16)/832×480(16:9)/624×624(1:1), 720p → 704×1280/1280×704/960×960 (32 배수 정렬은 구현 시 파이프라인 요구값으로 확정)
  - 산출물은 메모리에서만 처리. 고객 이미지·결과를 디스크에 영구 저장하지 않음(임시 파일은 생성 직후 삭제), 로그에 이미지·URL 미기록(§0.15)

### 4.2 `ml/serve.py` 변경

- `/video/i2v` POST: job 등록 → `{"job_id", "status": "QUEUED"}` 즉시 반환. `LOCAL_VIDEO_RENDER_COMMAND` 설정 시 기존 subprocess 경로 유지(하위호환) — 단 이 경로도 job 방식으로 감쌈.
- `/video/i2v/{job_id}` GET: `QUEUED|PROCESSING` → JSON, `SUCCEEDED` → `video/mp4` 바이트(1회 조회 후 메모리 해제), `FAILED` → JSON(오류 코드).
- 실행: 단일 백그라운드 워커 스레드 + in-process job dict. **전역 GPU 락**으로 `/restyle`(SD1.5 3.4GB)과 직렬화 — 동시 실행 시 8GB OOM 방지.
- 완료 job 은 TTL(예: 30분) 후 메모리에서 제거.

### 4.3 BE 변경 (`apimgr`)

- `SelfHostedWanVideoProvider`: submit → POST 응답의 job_id 를 external_job_id 로 반환(즉시). get_status → GET 폴링, MP4 바이트를 `VideoStatusResult.output_bytes` 로 반환. `_outputs` 인메모리 dict 제거(상태 원본이 ml 서버로 이동).
- `generations.py` 폴링 루프: 간격·횟수 env 화(§3.1). Mock 은 기존 기본값 유지(테스트 회귀 방지).
- `.env`: `DEFAULT_VIDEO_PROVIDER=SELF_HOSTED_WAN`, `LOCAL_VIDEO_TIMEOUT_SECONDS` 는 HTTP 왕복용으로 짧게 재조정(job 방식이므로 장시간 대기 불필요, 예 60초).
- 계약 주의(§5.1): provider 4상태·BE 10상태 매핑, FE Zod 스키마는 변경 없음(와이어 계약 동일). T2V(image 없음)를 `/video-generations` 로 열지는 구현 시 스키마 확인 후 결정 — 계약 변경이면 FE 와 함께 수정.

## 5. 오류 처리

- ml 서버: OOM·로드 실패·디코드 불가 → job FAILED + 내부 오류 코드(`LOCAL_VIDEO_RENDER_FAILED` 등). 원문 스택은 ml 로그에만.
- BE: FAILED 수신 시 상태 전이 규칙(§4.16)에 따라 FAILED 전이, FE 는 기존 오류 코드 UI.
- BE 폴링 한도 초과 → FAILED(TIMEOUT 성 오류 코드) 전이로 영구 PROCESSING 잔류 방지.
- 재시도: OOM·타임아웃은 자동 재시도하지 않음(동일 실패 반복·GPU 부하). 네트워크 순단만 폴링 자체가 흡수.

## 6. 검증 계획

1. 의존성 설치(`imageio-ffmpeg`, `gguf` — ml venv 한정, 사용자 승인 후) → **GGUF 로딩 스모크**: Q5_K_M 이 diffusers `from_single_file` 로 로드되는지(§리스크 R1).
2. 단독 스모크: 스크립트로 I2V·T2V 각 1회 생성 — 생성 시간·VRAM 피크 실측, 480p/720p 비교.
3. serve.py 경유: job 등록→폴링→MP4 수신, `/restyle` 동시 요청 시 직렬화 확인.
4. BE end-to-end: 202→폴링→SUCCEEDED→asset 다운로드. 새로고침 후 상태 복원(§3.8).
5. 회귀: `apimgr` pytest 전체, FE typecheck/build(계약 변경 시).
6. 실측표(시간·VRAM·품질) 보고 포함. 미확인 항목은 미확인으로 보고.

## 7. 리스크

- **R1**: QuantStack GGUF 가 diffusers 로딩과 호환되지 않을 가능성(모델 카드는 ComfyUI 기준) → 대안: bf16 가중치 + 그룹 오프로딩(RAM 64GB 로 가능, 속도 저하).
- **R2**: 5060 Ti 8GB 실측 벤치 부재 — 480p 5~10분/720p 15~30분은 추정치. 스모크 실측으로 기본 해상도 확정.
- **R3**: transformers 5.13.1 과 diffusers 0.39.0 조합의 umt5 로딩 호환 — 스모크에서 확인.
- **R4**: T2V 품질(춤 등 큰 동작)은 상용 API 대비 낮음 — seed 변경 다회 생성으로 보완, 사용자 고지 완료.

## 8. 범위 제외 (로드맵)

- 멀티 워커/분산 배포용 상태 저장소(Redis 등), Celery/RQ 큐
- 증류 LoRA·공격적 경량화(사용자가 품질 우선으로 보류)
- 1080p(모델 상한 초과), 8초 초과 영상
