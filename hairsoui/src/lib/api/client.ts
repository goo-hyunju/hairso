import type { z } from "zod";
import { API_ERROR_CODES, ApiError, type ApiErrorCode } from "./errors";

/**
 * 공통 API 클라이언트(§3.4) — Base URL·오류변환·requestId·Zod 검증을 한곳에서 처리.
 * 외부 AI Provider 를 FE 에서 직접 호출하지 않는다(§3.4). any 미사용(unknown + 타입가드).
 *
 * 취소·타임아웃: 호출자가 `signal`(AbortSignal)로 제어한다. **기본 타임아웃은 미구현(로드맵)** —
 * 필요 시 `AbortSignal.timeout(ms)` 를 넘긴다.
 * 오류 envelope(D2): { "error": { "error_code", "message", "request_id" } } (snake).
 * 성공 응답은 envelope 로 감싸지 않으므로 HTTP status 로 분기한다(비대칭).
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/**
 * 액세스 토큰 공급자(선택적 인증) — supabase-js 등 인증 클라이언트가 등록한다.
 * 미등록이면 토큰 없이(익명) 요청한다. BE 는 토큰이 있으면 검증해 created_by 를 채운다.
 * 예: `setAuthTokenProvider(async () => (await supabase.auth.getSession()).data.session?.access_token ?? null)`
 */
type AuthTokenProvider = () => string | null | Promise<string | null>;
let authTokenProvider: AuthTokenProvider | null = null;

export function setAuthTokenProvider(provider: AuthTokenProvider | null): void {
  authTokenProvider = provider;
}

function isApiErrorCode(value: unknown): value is ApiErrorCode {
  return typeof value === "string" && (API_ERROR_CODES as readonly string[]).includes(value);
}

function isAbortError(value: unknown): boolean {
  return (
    typeof value === "object" &&
    value !== null &&
    "name" in value &&
    (value as { name: unknown }).name === "AbortError"
  );
}

async function getHeaders(hasJsonBody: boolean): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};
  if (hasJsonBody) headers["Content-Type"] = "application/json";
  if (authTokenProvider) {
    try {
      const token = await authTokenProvider();
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch {
      // 토큰 획득 실패는 익명으로 진행(선택적 인증) — 요청 자체를 막지 않는다.
    }
  }
  return headers;
}

async function parseResponse<T>(res: Response, schema: z.ZodType<T>): Promise<T> {
  const headerRequestId = res.headers.get("x-request-id") ?? undefined;

  if (!res.ok) {
    let code: ApiErrorCode = "UNKNOWN";
    let bodyRequestId: string | undefined;
    try {
      const data: unknown = await res.json();
      if (typeof data === "object" && data !== null && "error" in data) {
        const err = (data as { error: unknown }).error;
        if (typeof err === "object" && err !== null) {
          const rec = err as Record<string, unknown>;
          if (isApiErrorCode(rec.error_code)) code = rec.error_code;
          if (typeof rec.request_id === "string") bodyRequestId = rec.request_id;
        }
      }
    } catch {
      // 본문 파싱 실패는 UNKNOWN 유지
    }
    throw new ApiError(code, res.status, bodyRequestId ?? headerRequestId);
  }

  // 204/빈 본문에서 res.json() 이 터지지 않도록 text 로 먼저 읽는다.
  const text = await res.text();
  let json: unknown;
  try {
    json = text ? (JSON.parse(text) as unknown) : undefined;
  } catch {
    // 성공 상태인데 본문이 깨진 JSON — 원시 SyntaxError 대신 ApiError 로 정규화(§3.12, #8).
    throw new ApiError("UNKNOWN", res.status, headerRequestId);
  }
  // 타입 단언이 아니라 런타임 검증(§3.5).
  return schema.parse(json);
}

export interface RequestOptions<T> {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  schema: z.ZodType<T>;
  signal?: AbortSignal;
}

export async function apiRequest<T>(path: string, options: RequestOptions<T>): Promise<T> {
  const { method = "GET", body, schema, signal } = options;

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: await getHeaders(body !== undefined),
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (isAbortError(err)) throw err;
    // 네트워크 오류 — Provider 원문 없이 코드만.
    throw new ApiError("UNKNOWN", 0);
  }

  return parseResponse(res, schema);
}

export interface FormRequestOptions<T> {
  method?: "POST" | "PATCH";
  formData: FormData;
  schema: z.ZodType<T>;
  signal?: AbortSignal;
}

export async function apiFormRequest<T>(
  path: string,
  options: FormRequestOptions<T>,
): Promise<T> {
  const { method = "POST", formData, schema, signal } = options;

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: await getHeaders(false),
      body: formData,
      signal,
    });
  } catch (err) {
    if (isAbortError(err)) throw err;
    throw new ApiError("UNKNOWN", 0);
  }

  return parseResponse(res, schema);
}
