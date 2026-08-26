import { z } from "zod";
import { API_ERROR_CODES } from "./errors";

/**
 * 와이어 계약 스키마 — BE Pydantic/DB 와 문자열 리터럴이 정확히 일치해야 하는 단일 출처.
 * 와이어 키는 snake_case(F8/D6). enum 은 z.enum 인라인(외부 튜플 주입 의존 제거 — zod3/4 양쪽 안전).
 * 값 변경 시 contract/enums.json 및 BE domain/enums.py 와 동기화(parity 테스트가 강제).
 */

// --- enum (계약 단일 출처) ---
export const generationStatusSchema = z.enum([
  "CREATED",
  "UPLOADING",
  "SUBMITTED",
  "QUEUED",
  "PROCESSING",
  "POST_PROCESSING",
  "SUCCEEDED",
  "FAILED",
  "CANCELED",
  "EXPIRED",
]);
export type GenerationStatus = z.infer<typeof generationStatusSchema>;
export const GENERATION_STATUSES = generationStatusSchema.options;

export const generationTypeSchema = z.enum(["IMAGE", "VIDEO"]);
export type GenerationType = z.infer<typeof generationTypeSchema>;

export const providerNameSchema = z.enum([
  "MOCK",
  "GEMINI",
  "PIXVERSE",
  "FAL_WAN",
  "WAN_CLOUD_API",
  "SELF_HOSTED_WAN",
  "LOCAL_SD",
]);
export type ProviderName = z.infer<typeof providerNameSchema>;

// 영상 provider 부분집합(GEMINI 제외 — GEMINI 는 이미지 분석/생성 소속, D4).
export const videoProviderNameSchema = z.enum([
  "PIXVERSE",
  "FAL_WAN",
  "WAN_CLOUD_API",
  "SELF_HOSTED_WAN",
  "MOCK",
]);
export type VideoProviderName = z.infer<typeof videoProviderNameSchema>;

export const imageProviderNameSchema = z.enum(["GEMINI", "MOCK", "LOCAL_SD"]);
export type ImageProviderName = z.infer<typeof imageProviderNameSchema>;

// 오류코드도 enum 으로 강제(status 응답 error_code parity — #13).
export const apiErrorCodeSchema = z.enum(API_ERROR_CODES);

export const studioTemplateTypeSchema = z.enum(["PROMOTION_SHORT", "SALON_EVENT_PROMOTION"]);
export type StudioTemplateType = z.infer<typeof studioTemplateTypeSchema>;

export const studioCategorySchema = z.enum([
  "HAIR",
  "BEAUTY",
  "HEALTH",
  "PRODUCT",
  "LOCAL_BUSINESS",
]);
export type StudioCategory = z.infer<typeof studioCategorySchema>;

export const studioToneSchema = z.enum(["CALM", "TRENDY", "PREMIUM", "FRIENDLY"]);
export type StudioTone = z.infer<typeof studioToneSchema>;

export const studioProjectStatusSchema = z.enum([
  "DRAFTING",
  "DRAFT_READY",
  "RENDERING",
  "SUCCEEDED",
  "FAILED",
]);
export type StudioProjectStatus = z.infer<typeof studioProjectStatusSchema>;

// --- 응답 스키마(snake_case, P6/P10) ---
export const generationStatusResponseSchema = z.object({
  generation_id: z.uuid(),
  generation_type: generationTypeSchema,
  status: generationStatusSchema,
  provider: providerNameSchema.nullable().optional(),
  estimated_cost_usd: z.number().nullable().optional(),
  output_asset_id: z.string().nullable().optional(),
  error_code: apiErrorCodeSchema.nullable().optional(),
});
export type GenerationStatusResponse = z.infer<typeof generationStatusResponseSchema>;

// 202 응답
export const videoGenerationResponseSchema = z.object({
  generation_id: z.uuid(),
  status: generationStatusSchema,
});
export type VideoGenerationResponse = z.infer<typeof videoGenerationResponseSchema>;

export const assetUploadResponseSchema = z.object({
  asset_id: z.string().min(1),
  asset_type: z.string().min(1),
  mime_type: z.string().min(1),
  byte_size: z.number().int().nonnegative(),
});
export type AssetUploadResponse = z.infer<typeof assetUploadResponseSchema>;

export const studioScriptSchema = z.object({
  hook: z.string().min(1),
  narration: z.array(z.string().min(1)).min(1).max(6),
  cta: z.string().min(1),
});
export type StudioScript = z.infer<typeof studioScriptSchema>;

export const studioSceneSchema = z.object({
  scene_index: z.number().int().min(1),
  duration_seconds: z.number().int().min(1),
  caption: z.string().min(1),
  visual_prompt: z.string().min(1),
});
export type StudioScene = z.infer<typeof studioSceneSchema>;

export const studioDraftSchema = z.object({
  version: z.number().int().positive(),
  script: studioScriptSchema,
  storyboard: z.array(studioSceneSchema).min(1).max(12),
  updated_at: z.string().min(1),
});
export type StudioDraft = z.infer<typeof studioDraftSchema>;

export const studioStorageConfigSchema = z.object({
  backend: z.string().min(1),
  storage_profile_name: z.string().min(1),
  output_prefix: z.string().min(1),
  output_retention_days: z.number().int().positive(),
});
export type StudioStorageConfig = z.infer<typeof studioStorageConfigSchema>;

export const studioProjectResponseSchema = z.object({
  project_id: z.uuid(),
  template_type: studioTemplateTypeSchema,
  category: studioCategorySchema,
  status: studioProjectStatusSchema,
  title: z.string().min(1),
  offer_text: z.string().min(1),
  cta_text: z.string().min(1),
  duration_seconds: z.union([z.literal(15), z.literal(30)]),
  target_audience: z.string().nullable().optional(),
  tone: studioToneSchema,
  asset_ids: z.array(z.string()),
  logo_asset_id: z.string().nullable().optional(),
  disclaimer: z.string().nullable().optional(),
  draft: studioDraftSchema.nullable().optional(),
  render_generation_id: z.string().nullable().optional(),
  render_status: generationStatusSchema.nullable().optional(),
  output_asset_id: z.string().nullable().optional(),
  storage: studioStorageConfigSchema,
  created_at: z.string().min(1),
  updated_at: z.string().min(1),
});
export type StudioProjectResponse = z.infer<typeof studioProjectResponseSchema>;

export const studioRenderResponseSchema = z.object({
  project_id: z.uuid(),
  generation_id: z.uuid(),
  status: generationStatusSchema,
});
export type StudioRenderResponse = z.infer<typeof studioRenderResponseSchema>;
