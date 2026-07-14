import { apiRequest } from "./client";
import {
  generationStatusResponseSchema,
  videoGenerationResponseSchema,
  type GenerationStatusResponse,
  type VideoGenerationResponse,
} from "./schemas";

/**
 * 생성 작업 API(§3.4). 상태 조회는 image/video 공통 정본 GET /api/v1/generations/{id}(D3/P10).
 */

export interface CreateVideoGenerationBody {
  consultation_id: string;
  image_asset_id: string;
  prompt: string;
  negative_prompt?: string;
  duration_seconds?: 5 | 8;
  aspect_ratio?: "9:16" | "16:9" | "1:1";
  quality?: "480p" | "720p" | "1080p";
  seed?: number;
  idempotency_key: string;
}

export async function createVideoGeneration(
  body: CreateVideoGenerationBody,
  signal?: AbortSignal,
): Promise<VideoGenerationResponse> {
  return apiRequest("/api/v1/video-generations", {
    method: "POST",
    body,
    schema: videoGenerationResponseSchema,
    signal,
  });
}

export async function getGenerationStatus(
  generationId: string,
  signal?: AbortSignal,
): Promise<GenerationStatusResponse> {
  return apiRequest(`/api/v1/generations/${generationId}`, {
    method: "GET",
    schema: generationStatusResponseSchema,
    signal,
  });
}
