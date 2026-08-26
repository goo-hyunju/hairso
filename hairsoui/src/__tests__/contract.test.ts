import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import {
  GENERATION_STATUSES,
  generationStatusSchema,
  generationTypeSchema,
  providerNameSchema,
  studioCategorySchema,
  studioProjectStatusSchema,
  studioTemplateTypeSchema,
  studioToneSchema,
  videoProviderNameSchema,
  imageProviderNameSchema,
} from "../lib/api/schemas";
import { API_ERROR_CODES } from "../lib/api/errors";

// F8 parity — FE Zod enum 이 계약 정본(contract/enums.json)과 문자열·순서까지 일치하는지.
const contract = JSON.parse(
  readFileSync(resolve(process.cwd(), "contract/enums.json"), "utf-8"),
) as Record<string, string[]>;

test("GenerationStatus parity (10)", () => {
  assert.deepEqual([...GENERATION_STATUSES], contract.GenerationStatus);
  assert.deepEqual([...generationStatusSchema.options], contract.GenerationStatus);
});

test("GenerationType parity", () => {
  assert.deepEqual([...generationTypeSchema.options], contract.GenerationType);
});

test("ProviderName parity (7)", () => {
  assert.deepEqual([...providerNameSchema.options], contract.ProviderName);
});

test("VideoProviderName parity (5, no GEMINI/LOCAL_SD)", () => {
  assert.deepEqual([...videoProviderNameSchema.options], contract.VideoProviderName);
  assert.ok(!videoProviderNameSchema.options.includes("GEMINI" as never));
  assert.ok(!videoProviderNameSchema.options.includes("LOCAL_SD" as never));
});

test("ImageProviderName parity", () => {
  assert.deepEqual([...imageProviderNameSchema.options], contract.ImageProviderName);
});

test("ErrorCode parity (18)", () => {
  assert.deepEqual([...API_ERROR_CODES], contract.ErrorCode);
});

test("StudioTemplateType parity", () => {
  assert.deepEqual([...studioTemplateTypeSchema.options], contract.StudioTemplateType);
});

test("StudioCategory parity", () => {
  assert.deepEqual([...studioCategorySchema.options], contract.StudioCategory);
});

test("StudioTone parity", () => {
  assert.deepEqual([...studioToneSchema.options], contract.StudioTone);
});

test("StudioProjectStatus parity", () => {
  assert.deepEqual([...studioProjectStatusSchema.options], contract.StudioProjectStatus);
});
