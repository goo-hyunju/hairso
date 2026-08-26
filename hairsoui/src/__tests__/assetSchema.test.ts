import { test } from "node:test";
import assert from "node:assert/strict";

import { assetUploadResponseSchema } from "../lib/api/schemas";

test("assetUploadResponseSchema 는 업로드 응답을 검증한다", () => {
  const parsed = assetUploadResponseSchema.parse({
    asset_id: "asset-1",
    asset_type: "FACE_SOURCE",
    mime_type: "image/png",
    byte_size: 128,
  });

  assert.equal(parsed.asset_id, "asset-1");
});

test("assetUploadResponseSchema 는 음수 byte_size 를 거부한다", () => {
  assert.throws(() =>
    assetUploadResponseSchema.parse({
      asset_id: "asset-1",
      asset_type: "FACE_SOURCE",
      mime_type: "image/png",
      byte_size: -1,
    }),
  );
});
