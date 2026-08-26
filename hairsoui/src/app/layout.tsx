import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hairso Studio",
  description: "카테고리 기반 AI 쇼츠 제작 스튜디오",
};

// Next 15 정식 방식: viewport 는 metadata 와 별도 export(metadata.viewport 는 deprecated).
// 확대 잠금(maximumScale/userScalable:false)은 접근성 회귀라 두지 않는다.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ko">
      <body className="min-h-dvh bg-[var(--ui-surface-page)] text-[var(--ui-content-primary)] antialiased">
        {children}
      </body>
    </html>
  );
}
