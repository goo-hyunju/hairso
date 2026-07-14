/**
 * 랜딩(Server Component) — 반응형 뼈대. 모드별(salon/public/admin) 화면은 로드맵.
 * mobile-first: base(모바일) -> sm/lg(태블릿·데스크톱). max-w-5xl 는 v3/v4 양쪽 유효 유틸.
 */
export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-5xl flex-col items-center justify-center gap-6 px-4 py-12 sm:px-6 lg:px-8">
      <h1 className="text-center text-3xl font-bold sm:text-4xl lg:text-5xl">HairView AI</h1>
      <p className="max-w-prose text-center text-base text-gray-600 sm:text-lg">
        AI 헤어스타일 상담 및 영상 시뮬레이션 — 스캐폴드
      </p>
    </main>
  );
}
