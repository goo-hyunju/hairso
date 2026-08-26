import type { ReactNode } from "react";

/**
 * 9:16 결과 미디어 래퍼 — 미용실 상담 상세·일반 모드·공개 결과 3곳에서 재사용(§3.11).
 * 컨테이너 폭은 부모가 반응형으로 제어(모바일=꽉참, 태블릿=중앙 고정폭).
 */

export interface AspectRatioMediaProps {
  children: ReactNode;
  className?: string;
}

export function AspectRatioMedia({ children, className = "" }: AspectRatioMediaProps) {
  return (
    <div className={`relative aspect-[9/16] w-full overflow-hidden rounded-lg bg-[var(--ui-surface-muted)] ${className}`}>
      {children}
    </div>
  );
}
