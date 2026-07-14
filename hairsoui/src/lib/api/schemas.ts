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

export const imageProviderNameSchema = z.enum(["GEMINI", "MOCK"]);
export type ImageProviderName = z.infer<typeof imageProviderNameSchema>;

// 오류코드도 enum 으로 강제(status 응답 error_code parity — #13).
export const apiErrorCodeSchema = z.enum(API_ERROR_CODES);

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
