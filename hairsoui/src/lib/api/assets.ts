import { apiFormRequest } from "./client";
import { assetUploadResponseSchema, type AssetUploadResponse } from "./schemas";

/**
 * 에셋 업로드 API. multipart/form-data boundary 는 브라우저가 설정해야 하므로
 * Content-Type 을 직접 지정하지 않는다.
 */

export async function uploadAsset(file: File, signal?: AbortSignal): Promise<AssetUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiFormRequest("/api/v1/assets", {
    method: "POST",
    formData,
    schema: assetUploadResponseSchema,
    signal,
  });
}
