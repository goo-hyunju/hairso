"""결정적 Studio draft provider.

기본 local/test 경로다. 같은 입력이면 같은 draft 를 만들어 회귀 테스트가 쉽다.
"""

from __future__ import annotations

from app.domain.enums import StudioCategory, StudioTemplateType, StudioTone
from app.domain.studio import StudioDraft, StudioScene, StudioScript
from app.providers.studio_draft.base import StudioDraftInput, StudioDraftProvider

_TONE_HOOK: dict[StudioTone, str] = {
    StudioTone.CALM: "차분한 분위기로 오늘의 소식을 소개해 보세요.",
    StudioTone.TRENDY: "지금 이 장면, 왜 눈길이 갈까요?",
    StudioTone.PREMIUM: "프리미엄한 경험의 차이를 짧게 보여 주세요.",
    StudioTone.FRIENDLY: "부담 없이 문의할 수 있는 소식을 따뜻하게 알려 보세요.",
}

_CATEGORY_LABEL: dict[StudioCategory, str] = {
    StudioCategory.HAIR: "헤어",
    StudioCategory.BEAUTY: "뷰티",
    StudioCategory.HEALTH: "건강 정보",
    StudioCategory.PRODUCT: "제품",
    StudioCategory.LOCAL_BUSINESS: "로컬 매장",
    StudioCategory.PET: "반려동물",
    StudioCategory.GENERAL: "일반",
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
        "Photorealistic product close-up vertical video, clear product composition, "
        "slow turntable motion, clean background, space for text overlay, 9:16"
    ),
    StudioCategory.LOCAL_BUSINESS: (
        "Photorealistic local shop atmosphere vertical video, warm service moment, "
        "friendly staff interaction, soft handheld motion, 9:16"
    ),
    StudioCategory.PET: (
        "Photorealistic pet vertical video, keep the animal identity and markings unchanged, "
        "natural small motion, cozy indoor lighting, 9:16"
    ),
    StudioCategory.GENERAL: (
        "Photorealistic vertical image-to-video shot, preserve the uploaded subject and composition, "
        "natural camera motion, realistic lighting, 9:16"
    ),
}

_TEMPLATE_NARRATION_PREFIX: dict[StudioTemplateType, str] = {
    StudioTemplateType.HAIR_STYLING_MOTION: "업로드한 사진을 기준으로 자연스러운 헤어 스타일링 움직임을 만듭니다.",
    StudioTemplateType.PROMOTION_SHORT: "짧은 콘텐츠의 핵심을 소개합니다.",
    StudioTemplateType.SALON_EVENT_PROMOTION: "기간이 있는 매장 소식을 빠르게 전해 드립니다.",
    StudioTemplateType.FREE_IMAGE_TO_VIDEO: "업로드한 이미지를 기준으로 짧은 움직임 영상을 만듭니다.",
}


class MockStudioDraftProvider(StudioDraftProvider):
    def create_draft(self, data: StudioDraftInput) -> StudioDraft:
        if data.template_type is StudioTemplateType.HAIR_STYLING_MOTION:
            return _build_hair_styling_draft(data)

        if data.template_type is StudioTemplateType.FREE_IMAGE_TO_VIDEO:
            return _build_free_i2v_draft(data)

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
            f"핵심 내용은 {data.offer_text}입니다.",
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


def _build_hair_styling_draft(data: StudioDraftInput) -> StudioDraft:
    styling_direction = data.offer_text
    keep_notes = data.disclaimer or "Keep face identity, hairline, hair color, and existing style natural."
    visual = (
        "Photorealistic hair styling image-to-video shot, preserve the uploaded person's face identity "
        "and hair structure, gentle head turn, subtle natural hair movement, realistic salon lighting, "
        f"styling direction: {styling_direction}, {keep_notes}, no text artifacts, stable 5 second vertical 9:16 motion"
    )
    narration = [
        _TEMPLATE_NARRATION_PREFIX[data.template_type],
        "얼굴과 헤어 라인을 바꾸지 않고 자연스럽게 움직입니다.",
        styling_direction,
    ]
    if data.target_audience:
        narration.append(data.target_audience)
    if data.disclaimer:
        narration.append(data.disclaimer)
    return StudioDraft(
        script=StudioScript(
            hook=data.title,
            narration=narration[:6],
            cta=data.cta_text,
        ),
        storyboard=[
            StudioScene(
                scene_index=1,
                duration_seconds=5,
                caption=data.title,
                visual_prompt=visual[:400],
            )
        ],
    )


def _build_free_i2v_draft(data: StudioDraftInput) -> StudioDraft:
    category_label = _CATEGORY_LABEL[data.category]
    motion = data.offer_text
    notes = data.disclaimer or "Preserve the uploaded subject identity and keep motion natural."
    visual = (
        f"{_CATEGORY_VISUAL[data.category]}, requested action: {motion}, "
        f"{notes}, no text artifacts, stable 5 second motion"
    )
    narration = [
        _TEMPLATE_NARRATION_PREFIX[data.template_type],
        f"{category_label} 이미지의 주 피사체를 유지합니다.",
        motion,
    ]
    if data.target_audience:
        narration.append(data.target_audience)
    if data.disclaimer:
        narration.append(data.disclaimer)
    return StudioDraft(
        script=StudioScript(
            hook=data.title,
            narration=narration[:6],
            cta=data.cta_text,
        ),
        storyboard=[
            StudioScene(
                scene_index=1,
                duration_seconds=5,
                caption=data.title,
                visual_prompt=visual[:400],
            )
        ],
    )


def _build_storyboard(data: StudioDraftInput) -> list[StudioScene]:
    if data.duration_seconds == 5:
        durations = [5]
    elif data.duration_seconds == 15:
        durations = [5, 5, 5]
    else:
        durations = [5, 6, 6, 8, 5]
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
    return f"{base}, detail scene, leave lower third space for Korean captions"
