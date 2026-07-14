# hairsoui — 코딩 컨벤션

## 컴포넌트 경계
- Server Component 기본. `"use client"` 는 브라우저 API(카메라·Canvas·파일·이벤트) 필요한 경계에만.
- 기능 단위는 `features/`, 공통 UI 는 `components/`. 페이지(`app/`)는 얇게.

## 타입·검증 (§3.5)
- `any` 금지(ESLint `@typescript-eslint/no-explicit-any: error`). 외부/BE 응답은 타입 단언 금지 → `schema.parse()`.
- 와이어 계약 타입 단일 출처 = `lib/api/schemas.ts`(Zod). `types/generation.ts` 는 재노출만(중복 정의 금지).

## 와이어/내부 표기 경계 (D17)
- **snake_case 는 와이어(Zod 키·API 경계)에 한정.** Zod parse 결과(snake 키)를 기본 소비.
- React props·훅 반환 등 FE 내부는 camelCase 허용. camel 재매핑이 불가피하면 **단일 매퍼로 국소화**(컴포넌트마다 산발 변환 금지).
- ESLint `camelcase` 규칙은 **비활성**(snake 접근 오탐 방지).

## 반응형 (P18)
- mobile-first **`base → sm → lg`**(실코드 기준 — landing 이 `sm:`/`lg:` 사용). 동적 className 금지(§3.10) — `sm:`/`lg:` 등 정적 prefix 만. 2주차 태블릿/모바일 레이아웃 분기 시 이 표기를 단일 기준으로 삼는다.
- Tailwind v4 유틸만 사용(`max-w-screen-*` 는 v4 deprecated → `max-w-5xl` 등). `min-h-dvh`·`aspect-[9/16]` 유효.
- 터치 타깃 최소 높이 `min-h-11`(공통 Button 상속).

## 오류 처리 (§3.12)
- 사용자 메시지는 `errorMessageView`(오류코드 기반). 미매핑 코드는 `UNKNOWN` 폴백. Stack Trace·Provider 원문·Storage Key·Internal ID 노출 금지.
- API 클라이언트는 오류 envelope `{ error: { error_code, message, request_id } }` 파싱, 성공은 HTTP status 로 분기.

## 개인정보 (§3.9)
- 고객 얼굴을 localStorage/sessionStorage/IndexedDB 에 저장 금지. 동의 없이 생성 API 호출 금지.
- (PWA 로드맵) 서비스워커에 고객 얼굴/결과 URL 캐싱 금지.

## 테스트
- `node --test` + `tsx`. alias(`@/`)는 런타임 미해석 → 테스트는 상대경로·`import type`(런타임 erase)만.
- parity 테스트가 Zod enum ↔ `contract/enums.json` 대조(F8).
