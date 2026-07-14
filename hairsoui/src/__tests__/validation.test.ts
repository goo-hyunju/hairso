import { test } from "node:test";
import assert from "node:assert/strict";

import {
  checkMimeType,
  checkFileSize,
  checkDimensions,
  validateImageMeta,
  MAX_FILE_BYTES,
} from "../lib/validation/image";

test("MIME 허용/거부", () => {
  assert.equal(checkMimeType("image/jpeg").ok, true);
  assert.equal(checkMimeType("image/gif").ok, false);
  assert.equal(checkMimeType("application/pdf").code, "MIME_NOT_ALLOWED");
});

test("파일 크기", () => {
  assert.equal(checkFileSize(MAX_FILE_BYTES).ok, true);
  assert.equal(checkFileSize(MAX_FILE_BYTES + 1).code, "TOO_LARGE");
});

test("해상도 최소치", () => {
  assert.equal(checkDimensions(512, 512).ok, true);
  assert.equal(checkDimensions(300, 800).code, "TOO_SMALL");
});

test("파이프라인은 첫 실패를 반환", () => {
  const r = validateImageMeta({ mime: "image/gif", bytes: 100, width: 1000, height: 1000 });
  assert.equal(r.code, "MIME_NOT_ALLOWED");
  const ok = validateImageMeta({ mime: "image/png", bytes: 100, width: 1000, height: 1000 });
  assert.equal(ok.ok, true);
});
