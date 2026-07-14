"""services — 비즈니스 규칙·트랜잭션 경계·Provider 선택(규칙 §4.3).

Router 는 여기로 위임한다. 외부 호출 중 DB 트랜잭션/락을 오래 잡지 않는다(§4.11).
services 는 domain·repositories·providers·core 를 import 한다(api import 금지).
"""
