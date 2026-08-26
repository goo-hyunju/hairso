import { generationStatusView, type StatusTone } from "@/features/video-generation/generationStatusView";
import type { GenerationStatus } from "@/types/generation";

const toneClass: Record<StatusTone, string> = {
  neutral: "bg-[var(--ui-status-neutral-bg)] text-[var(--ui-status-neutral-text)]",
  progress: "bg-[var(--ui-status-progress-bg)] text-[var(--ui-status-progress-text)]",
  success: "bg-[var(--ui-status-success-bg)] text-[var(--ui-status-success-text)]",
  error: "bg-[var(--ui-status-error-bg)] text-[var(--ui-status-error-text)]",
};

export interface StatusBadgeProps {
  status: GenerationStatus;
  showSpinner?: boolean;
  className?: string;
}

export function StatusBadge({ status, showSpinner = false, className = "" }: StatusBadgeProps) {
  const view = generationStatusView[status];
  return (
    <span
      className={`inline-flex min-h-7 items-center justify-center gap-2 rounded-full px-3 text-xs font-semibold ${toneClass[view.tone]} ${className}`}
      role="status"
      aria-live="polite"
    >
      <span>{view.label}</span>
      {showSpinner && !view.isTerminal && (
        <span
          className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:animate-none"
          aria-hidden="true"
        />
      )}
    </span>
  );
}
