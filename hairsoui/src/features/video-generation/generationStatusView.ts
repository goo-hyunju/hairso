import type { GenerationStatus } from "@/types/generation";

/**
 * 생성 상태 표시 Mapper(§3.8) — 화면 곳곳에서 문자열 비교 대신 이 단일 Mapper 만 참조.
 * Record<GenerationStatus, StatusView> 로 10개 상태 전부 강제(누락 시 컴파일 에러).
 *
 * 주: 상태 전이는 generation_type 별로 다르지만(IMAGE 엔 POST_PROCESSING 없음),
 * Mapper 는 어떤 상태가 오든 표시 문구를 보장하는 UI 안전망이므로 10키를 모두 유지한다.
 *
 * `isTerminal` 은 **UI 최종(더 진행 없음)** 의미다 — SUCCEEDED 포함. BE `state_machine.is_terminal`
 * 은 **전이-종료(outgoing 없음)** 로 SUCCEEDED 를 제외(SUCCEEDED→EXPIRED 존재)한다. 둘은 의도된 다른 개념.
 */

export type StatusTone = "neutral" | "progress" | "success" | "error";

export interface StatusView {
  label: string;
  tone: StatusTone;
  isTerminal: boolean;
}

export const generationStatusView: Record<GenerationStatus, StatusView> = {
  CREATED: { label: "생성 준비 중", tone: "neutral", isTerminal: false },
  UPLOADING: { label: "이미지 업로드 중", tone: "progress", isTerminal: false },
  SUBMITTED: { label: "AI 작업 요청 완료", tone: "progress", isTerminal: false },
  QUEUED: { label: "대기 중", tone: "progress", isTerminal: false },
  PROCESSING: { label: "영상을 생성하고 있어요", tone: "progress", isTerminal: false },
  POST_PROCESSING: { label: "영상 마무리 중", tone: "progress", isTerminal: false },
  SUCCEEDED: { label: "완료", tone: "success", isTerminal: true },
  FAILED: { label: "생성 실패", tone: "error", isTerminal: true },
  CANCELED: { label: "취소됨", tone: "error", isTerminal: true },
  EXPIRED: { label: "만료됨", tone: "error", isTerminal: true },
};

export function viewForStatus(status: GenerationStatus): StatusView {
  return generationStatusView[status];
}
