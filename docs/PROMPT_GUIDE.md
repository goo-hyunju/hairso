# PROMPT_GUIDE — 헤어스타일 생성 프롬프트

## 원칙
- **유지:** 얼굴 정체성·눈코입·피부톤·얼굴형·표정·의상·배경. **변경:** 길이·앞머리·가르마·컬·볼륨·색·레이어.
- 연예인 이름으로 얼굴 자체 변경 금지. 참고 사진에서 **헤어 특징만** 추출.

## 헤어 구조 JSON (분석 결과)
```json
{ "length": "jaw_length_bob", "bangs": "thin_see_through", "parting": "slightly_off_center",
  "curl": "soft_inward_c_curl", "crown_volume": "low", "side_volume": "medium",
  "color": "dark_chocolate_brown", "layer_position": "below_cheekbone", "overall_mood": "natural_elegant" }
```
잘못된 요청("아이유처럼") → 내부 변환("고객 얼굴/표정/피부톤/이목구비 유지, 참고에서 헤어 요소만 적용").

## 영상 프롬프트 (예시)
```text
Preserve the exact facial identity, features, skin tone, expression and hairstyle of the reference image.
The person slowly turns their head from front to a 35-degree angle. Subtle natural blinking.
Only the ends of the hair move gently. Soft professional salon lighting. Stable camera, realistic motion.
Do not change the face. Do not change the hairstyle during motion. No facial distortion. No sudden movement.
```
규격: 5초 · 9:16 · 720p · 16~24fps · 무음 · MP4.

## 금지 프롬프트 검사
- Gemini 로 금지/정책 위반 프롬프트 사전 검사(로드맵). 정책 위반 = GENERATION_POLICY_REJECTED(재시도 금지).

## 결과 안내 (필수 문구 취지)
> AI 로 생성한 예상 이미지입니다. 실제 시술 결과는 모질·모발 상태·두상·시술 방법에 따라 달라질 수 있습니다.
