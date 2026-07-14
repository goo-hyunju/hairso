# hairsoui — HairView AI Frontend (Next.js)

AI 헤어스타일 상담·영상 시뮬레이션 프론트엔드 스캐폴드. 진입점 문서: [`CLAUDE.md`](./CLAUDE.md).

## 빠른 시작
```bash
npm install
npm run dev        # http://localhost:3000
```

## 검증 (설치 시점 실측)
- `npm run typecheck` — exit 0 (strict + noUncheckedIndexedAccess)
- `npm run test` — **12 passed** (parity·mapper·validation)
- `npm run build` — exit 0 (Next.js 15.5.20, static / 생성)
- `npm run lint` — exit 0 (no-explicit-any: error)
- 설치 버전: next 15.5.20 · react 19.2.7 · zod 4.4.3 · tailwind 4.3.2

## 환경변수
`NEXT_PUBLIC_API_BASE_URL` — apimgr(BE) base URL. **미확정**(BE 포트/CORS 확정 후 주입).

## 구조
`src/{app,types,lib/api,lib/validation,features,components,__tests__}` + `contract/enums.json`.
하이브리드 반응형(웹+모바일 한 코드베이스, 네이티브 아님). 카메라·MediaPipe·모드별 화면은 로드맵([`docs/development-plan.md`](./docs/development-plan.md)).
