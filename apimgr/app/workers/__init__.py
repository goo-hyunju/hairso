"""workers — 오래 걸리는 작업(폴링·다운로드·후처리·만료)을 API 프로세스와 분리(규칙 §4.9).

스캐폴드에서는 폴링 루프 골격만 둔다. 실제 큐(초기 PostgreSQL Job 테이블)·FFmpeg·R2 는 로드맵.
무거운 영상 작업을 FastAPI BackgroundTasks 하나로 처리하지 않는다(§10 금지).
"""
