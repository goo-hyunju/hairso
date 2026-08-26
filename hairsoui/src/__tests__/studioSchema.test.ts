import { test } from "node:test";
import assert from "node:assert/strict";

import { studioProjectResponseSchema, studioRenderResponseSchema } from "../lib/api/schemas";

test("studioProjectResponseSchema 는 storage key 없이 Studio project 응답을 검증한다", () => {
  const parsed = studioProjectResponseSchema.parse({
    project_id: "11111111-1111-4111-8111-111111111111",
    template_type: "PROMOTION_SHORT",
    category: "HAIR",
    status: "DRAFT_READY",
    title: "봄맞이 클리닉 이벤트",
    offer_text: "첫 방문 20% 할인",
    cta_text: "오늘 예약 문의하기",
    duration_seconds: 15,
    target_audience: "신규 고객",
    tone: "FRIENDLY",
    asset_ids: [],
    logo_asset_id: null,
    disclaimer: null,
    draft: {
      version: 1,
      script: {
        hook: "이벤트를 소개합니다.",
        narration: ["첫 문장"],
        cta: "예약 문의",
      },
      storyboard: [
        {
          scene_index: 1,
          duration_seconds: 5,
          caption: "이벤트",
          visual_prompt: "salon vertical 9:16",
        },
      ],
      updated_at: "2026-08-05T00:00:00Z",
    },
    render_generation_id: null,
    render_status: null,
    output_asset_id: null,
    storage: {
      backend: "LOCAL_DISK",
      storage_profile_name: "local-dev",
      output_prefix: "studio/outputs",
      output_retention_days: 30,
    },
    created_at: "2026-08-05T00:00:00Z",
    updated_at: "2026-08-05T00:00:00Z",
  });

  assert.equal(parsed.template_type, "PROMOTION_SHORT");
  assert.equal(parsed.storage.output_prefix, "studio/outputs");
});

test("studioRenderResponseSchema 는 render job 응답을 검증한다", () => {
  const parsed = studioRenderResponseSchema.parse({
    project_id: "11111111-1111-4111-8111-111111111111",
    generation_id: "22222222-2222-4222-8222-222222222222",
    status: "SUBMITTED",
  });

  assert.equal(parsed.status, "SUBMITTED");
});
