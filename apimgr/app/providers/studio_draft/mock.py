"""결정적 Studio draft provider.

기본 local/test 경로다. 같은 입력이면 같은 draft 를 만들어 회귀 테스트가 쉽다.
"""

from __future__ import annotations

from app.domain.enums import StudioCategory, StudioTemplateType, StudioTone
from app.domain.studio import StudioDraft, StudioScene, StudioScript
from app.providers.studio_draft.base import StudioDraftInput, StudioDraftProvider


_TONE_HOOK: dict[StudioTone, str] = {
    StudioTone.CALM: "차분한 분위기로 오늘의 소식을 소개해 보세요.",
    StudioTone.TRENDY: "지금 이 혜택, 왜 놓치면 아쉬울까요?",
    StudioTone.PREMIUM: "프리미엄한 경험의 차이를 짧게 보여 주세요.",
    StudioTone.FRIENDLY: "부담 없이 문의할 수 있는 소식을 따뜻하게 알려 보세요.",
}

_CATEGORY_LABEL: dict[StudioCategory, str] = {
    StudioCategory.HAIR: "헤어",
    StudioCategory.BEAUTY: "뷰티",
    StudioCategory.HEALTH: "건강 정보",
    StudioCategory.PRODUCT: "제품",
    StudioCategory.LOCAL_BUSINESS: "로컬 매장",
}

_CATEGORY_VISUAL: dict[StudioCategory, str] = {
    StudioCategory.HAIR: (
        "Photorealistic hair salon vertical video, close-up styling detail, "
        "gentle camera push-in, natural hair movement, keep facial identity unchanged, 9:16"
    ),
    StudioCategory.BEAUTY: (
        "Photorealistic beauty studio vertical video, skincare or treatment detail, "
        "soft clean lighting, subtle hand movement, realistic texture, 9:16"
    ),
    StudioCategory.HEALTH: (
        "Clean editorial health information vertical video, simple abstract visual metaphor, "
        "calm camera movement, no medical diagnosis claim, 9:16"
    ),
    StudioCategory.PRODUCT: (
        "Photorealistic product close-up vertical video, clear benefit composition, "
        "slow turntable motion, clean background, space for text overlay, 9:16"
    ),
    StudioCategory.LOCAL_BUSINESS: (
        "Photorealistic local shop atmosphere vertical video, warm service moment, "
        "friendly staff interaction, soft handheld motion, 9:16"
    ),
}

_TEMPLATE_NARRATION_PREFIX: dict[StudioTemplateType, str] = {
    StudioTemplateType.PROMOTION_SHORT: "이번 프로모션의 핵심을 짧게 소개합니다.",
    StudioTemplateType.SALON_EVENT_PROMOTION: "기간 한정 이벤트 소식을 빠르게 전해 드립니다.",
}


class MockStudioDraftProvider(StudioDraftProvider):
    def create_draft(self, data: StudioDraftInput) -> StudioDraft:
        if data.template_type not in {
            StudioTemplateType.PROMOTION_SHORT,
            StudioTemplateType.SALON_EVENT_PROMOTION,
        }:
            raise ValueError("지원하지 않는 Studio draft template")

        audience = data.target_audience or "고객"
        category_label = _CATEGORY_LABEL[data.category]
        hook = f"{_TONE_HOOK[data.tone]} {data.title}"
        narration = [
            _TEMPLATE_NARRATION_PREFIX[data.template_type],
            f"{audience}을 위한 {category_label} 콘텐츠를 준비했습니다.",
            f"혜택은 {data.offer_text}입니다.",
            f"예약과 상담은 {data.cta_text}로 남겨 주세요.",
        ]
        if data.disclaimer:
            narration.append(data.disclaimer)
        narration = narration[:6]

        storyboard = _build_storyboard(data)
        return StudioDraft(
            script=StudioScript(hook=hook, narration=narration, cta=data.cta_text),
            storyboard=storyboard,
        )


def _build_storyboard(data: StudioDraftInput) -> list[StudioScene]:
    durations = [5, 5, 5] if data.duration_seconds == 15 else [5, 6, 6, 8, 5]
    scenes: list[StudioScene] = []
    for index, seconds in enumerate(durations, start=1):
        caption = _caption_for_scene(data, index, len(durations))
        visual = _visual_for_scene(data, index, len(durations))
        scenes.append(
            StudioScene(
                scene_index=index,
                duration_seconds=seconds,
                caption=caption,
                visual_prompt=visual,
            )
        )
    return scenes


def _caption_for_scene(data: StudioDraftInput, index: int, scene_count: int) -> str:
    if index == 1:
        return data.title
    if index == scene_count:
        return data.cta_text
    if data.category is StudioCategory.HEALTH and data.disclaimer:
        return data.disclaimer
    return data.offer_text


def _visual_for_scene(data: StudioDraftInput, index: int, scene_count: int) -> str:
    base = _CATEGORY_VISUAL[data.category]
    if index == 1:
        return base
    if index == scene_count:
        logo_note = " with optional logo placement" if data.has_logo else ""
        return (
            "Clear call-to-action end card for a vertical short"
            f"{logo_note}, clean typography-safe composition, 9:16"
        )
    if data.asset_count > 1:
        return f"{base}, use uploaded reference image variety, smooth transition between scenes"
    return f"{base}, benefit-focused detail scene, leave lower third space for Korean captions"

