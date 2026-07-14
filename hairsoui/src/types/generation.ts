/**
 * 도메인 타입 재노출 — 와이어 계약 타입의 단일 출처는 lib/api/schemas(Zod).
 * 중복 정의를 두지 않아 드리프트를 차단한다(§3.5).
 */
export type {
  GenerationStatus,
  GenerationType,
  ProviderName,
  VideoProviderName,
  ImageProviderName,
} from "@/lib/api/schemas";

export { GENERATION_STATUSES } from "@/lib/api/schemas";
