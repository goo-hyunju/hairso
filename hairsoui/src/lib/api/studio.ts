import { apiRequest } from "./client";
import {
  studioProjectResponseSchema,
  studioRenderResponseSchema,
  type StudioDraft,
  type StudioCategory,
  type StudioProjectResponse,
  type StudioRenderResponse,
  type StudioTemplateType,
  type StudioTone,
} from "./schemas";

/**
 * Studio API — project/draft/render 제품 계층.
 * FE 는 외부 AI Provider 를 직접 호출하지 않고 apimgr 의 mock/render job 만 호출한다.
 */

export interface CreateStudioProjectBody {
  template_type: StudioTemplateType;
  category: StudioCategory;
  title: string;
  offer_text: string;
  cta_text: string;
  duration_seconds: 15 | 30;
  target_audience?: string | null;
  tone: StudioTone;
  asset_ids: string[];
  logo_asset_id?: string | null;
  disclaimer?: string | null;
}

export interface UpdateStudioDraftBody {
  script: StudioDraft["script"];
  storyboard: StudioDraft["storyboard"];
}

export async function createStudioProject(
  body: CreateStudioProjectBody,
  signal?: AbortSignal,
): Promise<StudioProjectResponse> {
  return apiRequest("/api/v1/studio/projects", {
    method: "POST",
    body,
    schema: studioProjectResponseSchema,
    signal,
  });
}

export async function getStudioProject(
  projectId: string,
  signal?: AbortSignal,
): Promise<StudioProjectResponse> {
  return apiRequest(`/api/v1/studio/projects/${projectId}`, {
    method: "GET",
    schema: studioProjectResponseSchema,
    signal,
  });
}

export async function createStudioDraft(
  projectId: string,
  signal?: AbortSignal,
): Promise<StudioProjectResponse> {
  return apiRequest(`/api/v1/studio/projects/${projectId}/draft`, {
    method: "POST",
    schema: studioProjectResponseSchema,
    signal,
  });
}

export async function updateStudioDraft(
  projectId: string,
  body: UpdateStudioDraftBody,
  signal?: AbortSignal,
): Promise<StudioProjectResponse> {
  return apiRequest(`/api/v1/studio/projects/${projectId}/draft`, {
    method: "PATCH",
    body,
    schema: studioProjectResponseSchema,
    signal,
  });
}

export async function renderStudioProject(
  projectId: string,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<StudioRenderResponse> {
  return apiRequest(`/api/v1/studio/projects/${projectId}/render`, {
    method: "POST",
    body: { idempotency_key: idempotencyKey },
    schema: studioRenderResponseSchema,
    signal,
  });
}
