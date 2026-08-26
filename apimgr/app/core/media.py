"""미디어 바이트 검증 헬퍼.

외부 provider 결과를 에셋으로 저장하기 전에 최소한의 컨테이너 형식을 확인한다.
정밀한 코덱/재생 가능성 검증은 FFmpeg/ffprobe 단계에서 보강한다.
"""

from __future__ import annotations


def is_probable_mp4(data: bytes) -> bool:
    """MP4 컨테이너의 `ftyp` box 존재 여부를 작게 확인한다."""
    if len(data) < 12:
        return False
    return b"ftyp" in data[:32]
