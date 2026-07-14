# apimgr — 코딩 컨벤션

## 계층·의존 방향
- `api → services → repositories/providers → external`. `core` 는 leaf. `domain` 은 core 만 import.
- Router 에 SQL·외부 호출 금지. Service 가 비즈니스 규칙·트랜잭션 경계·Provider 선택.
- 외부 호출 중 DB 트랜잭션/락을 오래 잡지 않는다(§4.11).

## 모델 분리 (§4.5)
- DB(도메인 dataclass) / API(pydantic schemas) / Provider(각 base dataclass) 모델을 분리한다.
- 도메인 dataclass 필드명 = DDL 컬럼명 = **snake_case** (F8 정합).

## 와이어 계약
- 와이어 JSON 키는 **snake_case**. 오류 envelope: `{ "error": { "error_code", "message", "request_id" } }`.
- 성공 응답은 envelope 로 감싸지 않는다(비대칭 — 클라이언트는 HTTP status 로 분기).
- 날짜는 `timestamptz` ↔ ISO8601+TZ(§5.2). enum 은 문자열 리터럴(FE 와 동일, `contract/enums.json` 정본).

## 상태·Provider
- 상태 전이는 `state_machine.py` 한 곳. `can_transition`(bool, webhook no-op) / `assert_transition`(예외, 내부 버그).
- Provider 는 공통 base 인터페이스 뒤에. Service 는 Provider 전용 필드에 의존하지 않는다.
- 재시도: 도메인 예외의 `retryable` 플래그로 구분(429·일시 5xx = True / 잔액·정책·스키마 = False). 지수백오프(로드맵).

## enum 저장 (D10)
- Postgres 네이티브 ENUM 대신 `text` + `CHECK (... IN (...))`. 앱 enum ↔ CHECK 목록 동기화는 F8 게이트.

## 비용·크레딧 (§4.12 / D11)
- USD 원가 = `*_cost_usd`(generations). 크레딧 = `credit_transactions`(tx_type RESERVE/CHARGE/REFUND/ADJUST).
- 모든 금액은 `Decimal`/`numeric`. float 금지.

## 보안·개인정보
- 자격증명은 env(config)로만. 로그에 API Key·얼굴 URL·Base64 금지. `cfg/` 는 gitignore.
- 파일은 메타데이터만 DB 저장(원본 바이너리·공개 URL 금지, §4.13).

## 테스트
- 순수 계층은 `unittest`(오프라인). deps 계층은 pytest + FastAPI TestClient.
- 외부 사실값(가격·모델명·PixVerse 필드)은 코드에 `# unverified`/`# PLACEHOLDER` + env 분리.
