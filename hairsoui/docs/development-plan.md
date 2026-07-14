# hairsoui — 개발 계획 (로드맵)

기획서 §19 주차 계획을 FE 관점으로 매핑. 3구간 라벨로 구분.

## 이번 스캐폴드 `[구현·검증완료]`
- Next.js 15 App Router · TS strict · Tailwind v4 · Zod 설정 + 반응형 layout/landing.
- 타입/Zod 계약(`lib/api/schemas.ts`), 공통 API 클라이언트(`client.ts`), generations 함수.
- 상태 Mapper(10키), 오류코드→메시지(18키), 클라 이미지 검증 순수함수.
- 공통 컴포넌트 Button(터치 타깃)·AspectRatioMedia(9:16), `contract/enums.json`, parity/mapper/validation 테스트(12).
- 검증: typecheck 0 · test 12 · build 0 · lint 0.

## 로드맵 `[미구현-로드맵]`
- **2주차:** 브라우저 카메라 상태머신·실 스트림(getUserMedia)·track 정리, MediaPipe 품질검사, 촬영 가이드. (실기기 검증 필요 — §8.1)
- **3주차:** 업로드(Object URL→BE 발급→R2), 스타일 참고 UI, 이미지 3종 비교 UI, 재생성.
- **4주차:** 생성 상태 Polling 훅(StatusBadge + Mapper), 진행 UI, 새로고침 복원.
- **5주차:** 세 route group(salon/public/admin) 화면, QR/공유 결과 페이지(`share/[shareToken]`), 미용실 로고.
- **6주차:** 관리자 화면, 오류/재시도 UI, 배포. PWA(옵션 — 서비스워커 얼굴/결과 URL 캐싱 금지).

## 확인 필요 (사용자)
- ~~`NEXT_PUBLIC_API_BASE_URL`(BE 포트/CORS)~~ → **해소:** dev 는 빈 값(Next 프록시 `/api/*` → BE :8000, CORS 미사용). 루트 [`../../docs/LOCAL_DEV.md`](../../docs/LOCAL_DEV.md) 참조.
- 테스트 러너 확정(node --test 채택). UI 시안(현재 없음 → 정보구조 경계만 확정).
