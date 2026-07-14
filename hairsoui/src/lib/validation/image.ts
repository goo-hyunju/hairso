/**
 * 클라이언트 1차 이미지 검증(§3.7) — UX 개선용 순수 함수.
 * 보안 검증은 반드시 BE 에서 다시 수행한다(§3.7/§4.14).
 * decode(createImageBitmap) 등 브라우저 의존부는 별도 얇은 래퍼로 분리한다(로드맵).
 */

export const ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export type AllowedMimeType = (typeof ALLOWED_MIME_TYPES)[number];

export const MAX_FILE_BYTES = 10 * 1024 * 1024; // 10MB
export const MIN_DIMENSION = 512; // 얼굴이 너무 작지 않도록 최소 변 길이

export type ValidationCode =
  | "OK"
  | "MIME_NOT_ALLOWED"
  | "TOO_LARGE"
  | "TOO_SMALL";

export interface ValidationResult {
  ok: boolean;
  code: ValidationCode;
}

const OK: ValidationResult = { ok: true, code: "OK" };

export function checkMimeType(mime: string): ValidationResult {
  return (ALLOWED_MIME_TYPES as readonly string[]).includes(mime)
    ? OK
    : { ok: false, code: "MIME_NOT_ALLOWED" };
}

export function checkFileSize(bytes: number): ValidationResult {
  return bytes <= MAX_FILE_BYTES ? OK : { ok: false, code: "TOO_LARGE" };
}

export function checkDimensions(width: number, height: number): ValidationResult {
  return width >= MIN_DIMENSION && height >= MIN_DIMENSION
    ? OK
    : { ok: false, code: "TOO_SMALL" };
}

export interface FileMeta {
  mime: string;
  bytes: number;
  width: number;
  height: number;
}

/** 순수 검증 파이프라인 — 첫 실패를 반환한다. */
export function validateImageMeta(meta: FileMeta): ValidationResult {
  const checks = [
    checkMimeType(meta.mime),
    checkFileSize(meta.bytes),
    checkDimensions(meta.width, meta.height),
  ];
  return checks.find((r) => !r.ok) ?? OK;
}
