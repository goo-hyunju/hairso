import Link from "next/link";

const studioCards = [
  {
    title: "Promotion Short",
    body: "혜택, 가격, 시술 포인트를 15초 세로 쇼츠 초안으로 정리합니다.",
    meta: "Hair · 15s · Mock",
  },
  {
    title: "Event Promotion",
    body: "기간형 이벤트와 예약 CTA를 30초 스토리보드로 구성합니다.",
    meta: "Local · 30s · Mock",
  },
  {
    title: "Local AI Server",
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
                    미용실 프로모션, 이벤트, 상담 콘텐츠를 script와 storyboard 중심의 9:16 쇼츠 작업으로
                    만듭니다. 기본 경로는 Mock이라 유료 Provider 호출 없이 끝까지 확인할 수 있습니다.
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
                      <p className="text-2xl font-bold">첫 방문 클리닉</p>
                      <p className="mt-2 text-sm text-[var(--ui-content-inverse-muted)]">
                        후킹 문구, 씬, CTA를 먼저 편집합니다.
                      </p>
                    </div>
                    <div className="grid gap-2 text-[11px]">
                      <span className="rounded bg-[var(--ui-border-inverse)] px-2 py-1">Scene 01 · Hook</span>
                      <span className="rounded bg-[var(--ui-border-inverse)] px-2 py-1">Scene 02 · Offer</span>
                      <span className="rounded bg-[var(--ui-border-inverse)] px-2 py-1">Scene 03 · Booking</span>
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
              <p className="mt-2 font-semibold">Template → Draft → Render → Result</p>
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
