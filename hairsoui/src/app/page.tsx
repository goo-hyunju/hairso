import Link from "next/link";

const studioCards = [
  {
    title: "이미지 영상",
    body: "원하는 사진과 직접 쓴 프롬프트로 5~30초 세로 영상을 만듭니다.",
    meta: "Prompt · 5~30s · Local I2V",
  },
  {
    title: "헤어 스타일링",
    body: "얼굴, 헤어 라인, 모발 색을 유지하며 자연스러운 움직임을 만듭니다.",
    meta: "Hair · 5s · Local I2V",
  },
  {
    title: "로컬 AI 서버",
    body: "외부 프로그램은 Hairso API를 보고, Provider와 로컬 모델은 BE 뒤에 둡니다.",
    meta: "apimgr · backend-only",
  },
] as const;

export default function HomePage() {
  return (
    <main className="min-h-dvh bg-[var(--ui-surface-page)]">
      <section className="mx-auto grid min-h-dvh w-full max-w-7xl gap-6 px-4 py-4 sm:px-6 lg:grid-cols-[220px_minmax(0,1fr)] lg:px-8">
        <aside className="hidden rounded-lg bg-[var(--ui-surface-inverse)] p-4 text-[var(--ui-content-inverse)] lg:flex lg:flex-col">
          <Link href="/" className="text-xl font-bold">
            Hairso
          </Link>
          <nav className="mt-8 flex flex-col gap-2 text-sm">
            <Link className="rounded-lg bg-[var(--ui-border-inverse)] px-3 py-2 font-semibold" href="/studio">
              Studio
            </Link>
            <Link
              className="rounded-lg px-3 py-2 text-[var(--ui-content-inverse-muted)] hover:bg-[var(--ui-border-inverse)]"
              href="/try"
            >
              Mock Demo
            </Link>
          </nav>
          <div className="mt-auto rounded-lg border border-[var(--ui-border-inverse)] p-3 text-xs text-[var(--ui-content-inverse-muted)]">
            <p className="font-semibold text-[var(--ui-content-inverse)]">Server mode</p>
            <p className="mt-2">FE proxy → apimgr → local AI providers</p>
          </div>
        </aside>

        <div className="flex min-w-0 flex-col gap-5">
          <header className="studio-panel-elevated overflow-hidden">
            <div className="grid gap-6 p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:p-8">
              <div className="flex min-w-0 flex-col justify-between gap-8">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ui-action-accent)]">
                    Salon AI Video Studio
                  </p>
                  <h1 className="mt-3 max-w-3xl text-4xl font-bold leading-tight sm:text-5xl lg:text-6xl">
                    Hairso Studio
                  </h1>
                  <p className="mt-4 max-w-2xl text-base leading-7 text-[var(--ui-content-secondary)] sm:text-lg">
                    업로드한 이미지를 프롬프트 기반 9:16 영상으로 만들고, 필요하면 헤어 연출이나 매장 소식
                    템플릿으로 빠르게 시작합니다. Provider 호출과 로컬 모델 실행은 BE 뒤에 둡니다.
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <Link
                    href="/studio"
                    className="inline-flex min-h-11 items-center justify-center rounded-lg bg-[var(--ui-action-primary)] px-5 text-base font-semibold text-[var(--ui-action-on-primary)] transition-colors hover:bg-[var(--ui-action-primary-hover)]"
                  >
                    Studio 시작
                  </Link>
                  <Link
                    href="/try"
                    className="inline-flex min-h-11 items-center justify-center rounded-lg border border-[var(--ui-border-default)] bg-[var(--ui-surface-elevated)] px-5 text-base font-semibold text-[var(--ui-content-primary)] transition-colors hover:bg-[var(--ui-surface-muted)]"
                  >
                    내부 데모
                  </Link>
                </div>
              </div>

              <div className="rounded-lg bg-[var(--ui-surface-inverse)] p-4 text-[var(--ui-content-inverse)]">
                <div className="mx-auto aspect-[9/16] max-w-[220px] overflow-hidden rounded-lg bg-[var(--ui-surface-inverse)]">
                  <div className="studio-preview-canvas flex h-full flex-col justify-between p-4">
                    <div className="flex items-center justify-between text-[10px] text-[var(--ui-content-inverse-muted)]">
                      <span>9:16</span>
                      <span>Mock</span>
                    </div>
                    <div>
                      <p className="text-2xl font-bold">이미지 기반 영상</p>
                      <p className="mt-2 text-sm text-[var(--ui-content-inverse-muted)]">
                        이미지와 움직임 설명을 기준으로 짧은 MP4를 만듭니다.
                      </p>
                    </div>
                    <div className="grid gap-2 text-[11px]">
                      <span className="rounded bg-[var(--ui-border-inverse)] px-2 py-1">Scene 01 · Reference</span>
                      <span className="rounded bg-[var(--ui-border-inverse)] px-2 py-1">Motion · Prompt</span>
                      <span className="rounded bg-[var(--ui-border-inverse)] px-2 py-1">Output · MP4</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </header>

          <section className="grid gap-3 lg:grid-cols-3">
            {studioCards.map((card) => (
              <article key={card.title} className="studio-panel p-4">
                <p className="text-sm font-semibold text-[var(--ui-action-accent)]">{card.meta}</p>
                <h2 className="mt-3 text-xl font-bold">{card.title}</h2>
                <p className="mt-2 text-sm leading-6 text-[var(--ui-content-secondary)]">{card.body}</p>
              </article>
            ))}
          </section>

          <section className="studio-panel grid gap-4 p-4 sm:grid-cols-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ui-content-muted)]">
                Pipeline
              </p>
              <p className="mt-2 font-semibold">템플릿 → 초안 → 렌더 → 결과</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ui-content-muted)]">
                Boundary
              </p>
              <p className="mt-2 font-semibold">Provider calls stay in apimgr</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ui-content-muted)]">
                Output
              </p>
              <p className="mt-2 font-semibold">asset_id reference, no signed URL</p>
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
