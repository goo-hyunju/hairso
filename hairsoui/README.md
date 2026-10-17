# hairsoui — Hairso Studio Frontend (Next.js)

AI 쇼츠 제작 스튜디오의 프론트엔드. 컨벤션: [`docs/conventions.md`](./docs/conventions.md) · 화면 흐름: [`docs/USER_FLOWS.md`](./docs/USER_FLOWS.md).

## 빠른 시작
```bash
npm install
npm run dev        # http://localhost:3000
```

## 검증 (2026-10-17 실행)
- `npm run typecheck` — exit 0 (strict + noUncheckedIndexedAccess)
- `npm run test` — **20 passed**(parity·mapper·validation·studio schema, 5파일)
- `npm run build` — exit 0 (Next.js 15.5.20, static / 생성)
- `npm run lint` — exit 0 (no-explicit-any: error)
- 설치 버전: next 15.5.20 · react 19.2.7 · zod 4.4.3 · tailwind 4.3.2

## 환경변수
`NEXT_PUBLIC_API_BASE_URL` — dev 기본은 빈 값. Next rewrite가 `/api/*`를 apimgr `127.0.0.1:8000`으로 프록시한다. 운영 게이트웨이가 확정되면 별도 주입한다.

## 구조
`src/{app,types,lib/api,lib/validation,features,components,__tests__}` + `contract/enums.json`.
하이브리드 반응형(웹+모바일 한 코드베이스, 네이티브 아님). 카메라·MediaPipe·모드별 화면은 로드맵([`docs/development-plan.md`](./docs/development-plan.md)).
