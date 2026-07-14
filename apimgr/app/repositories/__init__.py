"""repositories — DB 조회/저장/락 캡슐화(규칙 §4.3).

스캐폴드에서는 실 DB 미연결. 인터페이스(ABC) + 인메모리 구현을 둔다.
실 DB(PostgreSQL) 연동·스키마 실행은 사용자 관리(규칙 §4.19) — 로드맵.
repositories 는 domain·core 만 import 한다(api import 금지).
"""
