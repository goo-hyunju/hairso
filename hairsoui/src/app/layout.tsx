import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "HairView AI",
  description: "AI 헤어스타일 상담 및 영상 시뮬레이션",
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
      <body className="min-h-dvh bg-white text-gray-900 antialiased">{children}</body>
    </html>
  );
}
