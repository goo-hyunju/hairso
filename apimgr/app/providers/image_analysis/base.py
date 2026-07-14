"""이미지 분석 Provider 공통 인터페이스.

참고 사진에서 헤어 구조만 추출한다(연예인 이름·정체성 미저장, 규칙 §6.1/§18).
분석은 단발성 호출(짧음) → 동기 반환(작업 큐 불필요, 규칙 §4.11 트랜잭션 밖 호출).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class HairStructure:
    """헤어 구조 JSON(§5 단계4). 연예인 이름은 담지 않는다."""

    length: str
    bangs: str
    parting: str
    curl: str
    crown_volume: str
    side_volume: str
    color: str
    layer_position: str
    overall_mood: str

    def to_dict(self) -> dict[str, str]:
        return {
            "length": self.length,
            "bangs": self.bangs,
            "parting": self.parting,
            "curl": self.curl,
            "crown_volume": self.crown_volume,
            "side_volume": self.side_volume,
            "color": self.color,
            "layer_position": self.layer_position,
            "overall_mood": self.overall_mood,
        }


@dataclass(frozen=True)
class StyleAnalysisInput:
    reference_asset_id: str
    text_hint: str | None = None


@dataclass(frozen=True)
class StyleAnalysisResult:
    structure: HairStructure
    warnings: list[str] = field(default_factory=list)


class ImageAnalysisProvider(ABC):
    @abstractmethod
    async def analyze_style(self, data: StyleAnalysisInput) -> StyleAnalysisResult:
        ...
