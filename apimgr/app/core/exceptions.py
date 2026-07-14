"""애플리케이션 예외의 베이스 (제네릭·비즈니스 무지식)."""

from __future__ import annotations


class AppError(Exception):
    """모든 애플리케이션 예외의 최상위 베이스.

    core 는 도메인을 모르므로 여기엔 error_code 같은 도메인 개념을 두지 않는다.
    도메인 예외(app.domain.errors)가 이 클래스를 상속해 error_code 를 덧붙인다.
    """


class ConfigError(AppError):
    """설정/환경변수 관련 오류 (제네릭)."""
