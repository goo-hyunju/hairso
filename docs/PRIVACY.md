# PRIVACY — 개인정보

## 얼굴 사진 = 개인정보(생체인식정보 가능성)
- 고객 인증 목적으로 얼굴 특징을 처리하지 않고, 얼굴 임베딩을 장기 저장하지 않는다.

## 필수 정책 (기획서 §18)
- AI 처리 목적 명시 · 외부 AI 전송 사실 안내 · 저장 기간 안내 · 삭제/철회 기능 · 원본 암호화 · 접근 기록 · 외부 공개 기본 차단.

## 저장 기간
- 참고(연예인) 사진: 분석 직후 삭제. 고객 원본: 기본 24h 또는 상담 종료 후. 결과: 7~30일(고객 선택). 상담 기록: 사진 없이 텍스트 중심.

## 동의 (consents 테이블)
- 유형: FACE_PROCESSING / EXTERNAL_AI_TRANSFER / STORAGE / RESULT_SHARE. **동의 없으면 생성 API 호출 금지 → CONSENT_REQUIRED**.
- FE: 얼굴을 localStorage/sessionStorage/IndexedDB 저장 금지. PWA 서비스워커 얼굴/결과 URL 캐싱 금지.

## 저작권 (연예인 참고 사진)
- 참고 사진은 일시 업로드 → 헤어 요소만 JSON 추출 → 원본 삭제 → 이름 프롬프트 제거 → 스타일 설명만 저장.
- 서비스가 연예인 카탈로그 제공/광고 금지. 기본 카탈로그는 자체 촬영·라이선스·AI 가상모델·상업허용 자료만.

## 로그
- 얼굴 URL·Base64·전화번호 원문 로그 금지. 필요 시 asset_id/generation_id/consultation_id 만.
