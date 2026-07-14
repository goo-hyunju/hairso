# hairsoui — 사용자 흐름 · 정보구조

## 두 축의 분리 (반드시 준수)
- **라우트 분리축 (인증/진입맥락)** — App Router route group:
  - `(salon)` : 미용실 상담 모드(직원 인증, 태블릿/데스크톱 상담 컨텍스트).
  - `(public)` : 일반 사용자 모드(익명, 모바일 웹 단일 흐름).
  - `(admin)` : 관리자 모드.
  - `share/[shareToken]` : **인증 없는 공개 결과 경로 → route group 밖 최상위**(§3.3 Server 초기 로딩). salon 그룹에 넣지 않는다(인증 레이아웃 오염 방지).
- **반응형 축 (디바이스 폭)** — 각 그룹 **내부에서** Tailwind breakpoint(`base→sm→lg`, 실코드 기준)로. `useMediaQuery` 로 레이아웃 통째 교체 금지(hydration mismatch).
- 두 축을 섞지 않는다: "직원이냐 익명이냐"=라우트, "태블릿이냐 모바일이냐"=CSS.

## 핵심 상담 흐름 (기획서 §5) — features 로 재사용
촬영(camera) → 품질검사(camera/validation) → 참고입력(style-analysis) → 구조분석 → 추천 → 이미지 3종(image-generation) → 영상(video-generation) → 공유(result-share).
- 미용실 모드: 상담 컨텍스트(`consultations/[id]`) 안 다단계. 일반 모드: 단일 위저드(`try`). 각 단계는 페이지가 아닌 **features 컴포넌트**로 두 모드 공유.

## 이번 스캐폴드 상태
- `[구현·검증완료]`: 반응형 landing(`/`), layout(viewport), 공통 컴포넌트(Button·AspectRatioMedia), 상태 Mapper, 오류 매핑, 클라 검증 순수함수.
- `[미구현-로드맵]`: 위 route group·모드별 화면·카메라 실동작·MediaPipe·업로드·Polling. 이 문서의 정보구조를 2~5주차에 구현.

## 결과 뷰
9:16 결과는 `components/AspectRatioMedia`(공통) 재사용 — 상담 상세·일반 모드·공개 페이지 3곳. 컨테이너 폭만 반응형.
