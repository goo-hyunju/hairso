import { GenerationFlow } from "@/features/video-generation/GenerationFlow";

/**
 * /try — 일반 사용자 모드 데모 화면(Server Component 껍데기 + Client 흐름).
 * 카메라 없이 Mock 백엔드로 생성 흐름을 끝까지 돌려볼 수 있다. 촬영·실 AI·QR은 로드맵.
 */
export default function TryPage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col items-center px-4 py-10 sm:px-6 sm:py-14">
      <header className="mb-8 text-center">
        <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ui-action-accent)]">
          데모 · Mock 백엔드
        </p>
        <h1 className="mt-2 text-3xl font-bold sm:text-4xl">헤어 영상 생성해 보기</h1>
        <p className="mx-auto mt-3 max-w-prose text-[var(--ui-content-secondary)]">
          스타일을 입력하고 생성을 누르면 요청부터 완료까지 실제로 진행됩니다. 지금은 모의(Mock)
          생성이며, 카메라 촬영·실제 이미지/영상·QR 공유는 다음 단계입니다.
        </p>
      </header>
      <GenerationFlow />
    </main>
  );
}
