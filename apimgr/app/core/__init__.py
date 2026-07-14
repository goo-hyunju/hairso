"""core — 제네릭 인프라 계층 (leaf).

이 패키지는 app 내부의 어떤 모듈도 import 하지 않는다(도메인 무지식).
따라서 GenerationStatus·ErrorCode 등 도메인 개념은 여기 두지 않고 domain 에 둔다.
(규칙: core -> domain import 금지. `grep "from app.domain" app/core` == 0)
"""
