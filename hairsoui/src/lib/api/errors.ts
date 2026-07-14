/**
 * 오류코드 -> 사용자 메시지 매핑(§3.12/§5.3 + 보강 = 18개). BE ErrorCode 와 동일 리터럴.
 * Record<ApiErrorCode, string> 로 누락 시 컴파일 에러(완전성 강제).
 * 사용자 메시지에 Provider 원문·스택·Storage Key 를 노출하지 않는다(§3.12).
 */

export const API_ERROR_CODES = [
  // §5.3 기본
  "ASSET_INVALID",
  "ASSET_NOT_FOUND",
  "CONSENT_REQUIRED",
  "GENERATION_DUPLICATED",
  "PROVIDER_RATE_LIMITED",
  "PROVIDER_BALANCE_EXHAUSTED",
  "GENERATION_POLICY_REJECTED",
  "GENERATION_FAILED",
  "WEBHOOK_SIGNATURE_INVALID",
  // 보강
  "UNAUTHORIZED",
  "FORBIDDEN",
  "VALIDATION_ERROR",
  "NOT_FOUND",
  "CREDIT_INSUFFICIENT",
  "SHARE_EXPIRED",
  "DOWNLOAD_FAILED",
  "INTERNAL_ERROR",
  "UNKNOWN",
] as const;

export type ApiErrorCode = (typeof API_ERROR_CODES)[number];

export const errorMessageView: Record<ApiErrorCode, string> = {
  ASSET_INVALID: "사진 형식이나 용량을 확인해 주세요.",
  ASSET_NOT_FOUND: "사진을 찾을 수 없어요. 다시 업로드해 주세요.",
  CONSENT_REQUIRED: "개인정보 동의 후 이용할 수 있어요.",
  GENERATION_DUPLICATED: "이미 진행 중인 생성 요청이 있어요.",
  PROVIDER_RATE_LIMITED: "요청이 많아요. 잠시 후 다시 시도해 주세요.",
  PROVIDER_BALANCE_EXHAUSTED: "생성 한도를 초과했어요. 관리자에게 문의해 주세요.",
  GENERATION_POLICY_REJECTED: "정책상 생성할 수 없는 요청이에요.",
  GENERATION_FAILED: "생성에 실패했어요. 다시 시도해 주세요.",
  WEBHOOK_SIGNATURE_INVALID: "요청을 처리할 수 없어요.",
  UNAUTHORIZED: "로그인이 필요해요.",
  FORBIDDEN: "접근 권한이 없어요.",
  VALIDATION_ERROR: "입력값을 다시 확인해 주세요.",
  NOT_FOUND: "요청한 정보를 찾을 수 없어요.",
  CREDIT_INSUFFICIENT: "크레딧이 부족해요.",
  SHARE_EXPIRED: "공유 링크가 만료됐어요.",
  DOWNLOAD_FAILED: "결과를 불러오지 못했어요. 다시 시도해 주세요.",
  INTERNAL_ERROR: "일시적인 오류가 발생했어요. 잠시 후 다시 시도해 주세요.",
  UNKNOWN: "일시적인 오류가 발생했어요. 잠시 후 다시 시도해 주세요.",
};

export function messageForErrorCode(code: ApiErrorCode): string {
  return errorMessageView[code];
}

export class ApiError extends Error {
  constructor(
    public readonly code: ApiErrorCode,
    public readonly status: number,
    public readonly requestId?: string,
  ) {
    super(code);
    this.name = "ApiError";
  }
}
