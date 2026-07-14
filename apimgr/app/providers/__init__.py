"""providers — 외부 AI Provider 추상화. 공통 인터페이스(base) 뒤에 구현을 둔다(규칙 §4.6).

Service 는 특정 Provider 전용 필드에 의존하지 않는다. Provider 내부에서 변환한다.
providers 는 domain·core 만 import 한다(api/services import 금지).
"""
