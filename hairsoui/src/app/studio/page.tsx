import { StudioFlow } from "@/features/studio/StudioFlow";

/**
 * /studio — 카테고리 기반 Promotion Short Studio 작업 화면.
 * 페이지는 Server Component shell 이고, 입력·편집·polling 은 Client Component 로 분리한다.
 */
export default function StudioPage() {
  return (
    <main className="min-h-dvh bg-[var(--ui-surface-page)]">
      <StudioFlow />
    </main>
  );
}
