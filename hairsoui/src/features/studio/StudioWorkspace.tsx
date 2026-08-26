"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { AspectRatioMedia } from "@/components/AspectRatioMedia";
import { Button } from "@/components/Button";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError, messageForErrorCode } from "@/lib/api/errors";
import { getGenerationStatus } from "@/lib/api/generations";
import {
  createStudioDraft,
  createStudioProject,
  getStudioProject,
  renderStudioProject,
  updateStudioDraft,
} from "@/lib/api/studio";
import type {
  GenerationStatus,
  StudioCategory,
  StudioProjectResponse,
  StudioTemplateType,
  StudioTone,
} from "@/lib/api/schemas";

const TERMINAL: ReadonlySet<GenerationStatus> = new Set<GenerationStatus>([
  "SUCCEEDED",
  "FAILED",
  "CANCELED",
  "EXPIRED",
]);

const STUDIO_ASSET_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;

const toneLabels: Record<StudioTone, string> = {
  CALM: "차분",
  TRENDY: "트렌디",
  PREMIUM: "프리미엄",
  FRIENDLY: "친근",
};

const categoryLabels: Record<StudioCategory, string> = {
  HAIR: "Hair",
  BEAUTY: "Beauty",
  HEALTH: "Health",
  PRODUCT: "Product",
  LOCAL_BUSINESS: "Local",
};

const flowSteps = [
  { id: "templates", label: "Template", detail: "작업 유형" },
  { id: "draft", label: "Draft", detail: "대본·씬" },
  { id: "render", label: "Render", detail: "생성 작업" },
  { id: "result", label: "Result", detail: "결과 참조" },
] as const;

const templateLabels: Record<StudioTemplateType, string> = {
  PROMOTION_SHORT: "Promotion Short",
  SALON_EVENT_PROMOTION: "Event Promotion",
};

interface StudioTemplateOption {
  template_type: StudioTemplateType;
  category: StudioCategory;
  title: string;
  summary: string;
  duration_seconds: 15 | 30;
  offer_text: string;
  cta_text: string;
  target_audience: string;
  tone: StudioTone;
  disclaimer: string;
}

const defaultTemplateOption: StudioTemplateOption = {
  template_type: "PROMOTION_SHORT",
  category: "HAIR",
  title: "봄맞이 클리닉 이벤트",
  summary: "혜택, 가격, CTA를 15초 세로 쇼츠로 정리합니다.",
  duration_seconds: 15,
  offer_text: "첫 방문 20% 할인, 이번 달 한정",
  cta_text: "오늘 예약 문의하기",
  target_audience: "신규 고객",
  tone: "FRIENDLY",
  disclaimer: "상세 조건은 매장 상담 후 확정됩니다.",
};

const templateOptions: StudioTemplateOption[] = [
  defaultTemplateOption,
  {
    template_type: "SALON_EVENT_PROMOTION",
    category: "LOCAL_BUSINESS",
    title: "주말 예약 오픈 이벤트",
    summary: "기간형 이벤트와 매장 방문 유도를 30초 흐름으로 보여줍니다.",
    duration_seconds: 30,
    offer_text: "이번 주말 예약 고객 전용 케어 업그레이드",
    cta_text: "가능 시간 확인하기",
    target_audience: "근처 방문 고객",
    tone: "TRENDY",
    disclaimer: "이벤트 수량과 시간은 매장 상황에 따라 달라질 수 있습니다.",
  },
];

const serverRoute = [
  "External user",
  "Hairso FE",
  "apimgr",
  "Local AI",
] as const;

type Phase = "idle" | "drafting" | "editing" | "rendering" | "done" | "error";
type FlowStep = (typeof flowSteps)[number]["id"];

function resolveFlowStep(phase: Phase, project: StudioProjectResponse | null): FlowStep {
  if (phase === "done" || (phase === "error" && project?.render_generation_id)) return "result";
  if (phase === "rendering" || project?.render_generation_id) return "render";
  if (phase === "drafting" || project?.draft) return "draft";
  return "templates";
}

function getTemplateOption(templateType: StudioTemplateType) {
  return templateOptions.find((option) => option.template_type === templateType) ?? defaultTemplateOption;
}

function isAbortError(err: unknown): boolean {
  return (
    typeof err === "object" &&
    err !== null &&
    "name" in err &&
    (err as { name: unknown }).name === "AbortError"
  );
}

function toNullable(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function parseAssetIds(value: string): string[] {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 6);
}

function hasInvalidAssetReference(assetIds: string[], logoAssetId: string | null): boolean {
  return (
    assetIds.some((assetId) => !STUDIO_ASSET_ID_PATTERN.test(assetId)) ||
    (logoAssetId !== null && !STUDIO_ASSET_ID_PATTERN.test(logoAssetId))
  );
}

interface StudioSectionProps {
  eyebrow?: string;
  title: string;
  body?: string;
  action?: ReactNode;
  children: ReactNode;
}

function StudioSection({ eyebrow, title, body, action, children }: StudioSectionProps) {
  return (
    <section className="studio-panel-elevated p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          {eyebrow && (
            <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ui-action-accent)]">
              {eyebrow}
            </p>
          )}
          <h2 className="mt-1 text-lg font-bold">{title}</h2>
          {body && <p className="mt-1 text-sm leading-6 text-[var(--ui-content-secondary)]">{body}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

interface FieldProps {
  label: string;
  hint?: string;
  children: ReactNode;
}

function Field({ label, hint, children }: FieldProps) {
  return (
    <label className="flex flex-col gap-1">
      <span className="studio-label">{label}</span>
      {children}
      {hint && <span className="text-xs text-[var(--ui-content-muted)]">{hint}</span>}
    </label>
  );
}

interface DetailRowProps {
  label: string;
  value: ReactNode;
  mono?: boolean;
}

function DetailRow({ label, value, mono = false }: DetailRowProps) {
  return (
    <div className="flex min-h-11 items-center justify-between gap-3 border-t border-[var(--ui-border-default)] py-3 text-sm first:border-t-0">
      <span className="shrink-0 font-semibold text-[var(--ui-content-muted)]">{label}</span>
      <span
        className={`min-w-0 break-words text-right font-semibold text-[var(--ui-content-primary)] ${
          mono ? "font-mono text-xs" : ""
        }`}
      >
        {value}
      </span>
    </div>
  );
}

export function StudioWorkspace() {
  const [selectedTemplate, setSelectedTemplate] = useState<StudioTemplateType>(
    defaultTemplateOption.template_type,
  );
  const [title, setTitle] = useState(defaultTemplateOption.title);
  const [offerText, setOfferText] = useState(defaultTemplateOption.offer_text);
  const [ctaText, setCtaText] = useState(defaultTemplateOption.cta_text);
  const [durationSeconds, setDurationSeconds] = useState<15 | 30>(
    defaultTemplateOption.duration_seconds,
  );
  const [targetAudience, setTargetAudience] = useState(defaultTemplateOption.target_audience);
  const [category, setCategory] = useState<StudioCategory>(defaultTemplateOption.category);
  const [tone, setTone] = useState<StudioTone>(defaultTemplateOption.tone);
  const [assetIdsText, setAssetIdsText] = useState("");
  const [logoAssetId, setLogoAssetId] = useState("");
  const [disclaimer, setDisclaimer] = useState(defaultTemplateOption.disclaimer);

  const [project, setProject] = useState<StudioProjectResponse | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [generationStatus, setGenerationStatus] = useState<GenerationStatus | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mounted = useRef(true);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abort = useRef<AbortController | null>(null);
  const renderKey = useRef<string | null>(null);

  const cleanup = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    abort.current?.abort();
  }, []);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      cleanup();
    };
  }, [cleanup]);

  const setApiError = useCallback((err: unknown) => {
    if (isAbortError(err)) return;
    const code = err instanceof ApiError ? err.code : "UNKNOWN";
    setErrorMsg(messageForErrorCode(code));
    setPhase("error");
  }, []);

  const resetRenderState = useCallback(() => {
    setProject(null);
    setGenerationStatus(null);
    setErrorMsg(null);
    setPhase("idle");
    renderKey.current = null;
  }, []);

  const handleSelectTemplate = useCallback(
    (templateType: StudioTemplateType) => {
      if (phase === "drafting" || phase === "rendering") return;
      cleanup();
      const option = getTemplateOption(templateType);
      setSelectedTemplate(option.template_type);
      setCategory(option.category);
      setTitle(option.title);
      setOfferText(option.offer_text);
      setCtaText(option.cta_text);
      setDurationSeconds(option.duration_seconds);
      setTargetAudience(option.target_audience);
      setTone(option.tone);
      setDisclaimer(option.disclaimer);
      resetRenderState();
    },
    [cleanup, phase, resetRenderState],
  );

  const handleStartOver = useCallback(() => {
    const option = getTemplateOption(selectedTemplate);
    cleanup();
    setCategory(option.category);
    setTitle(option.title);
    setOfferText(option.offer_text);
    setCtaText(option.cta_text);
    setDurationSeconds(option.duration_seconds);
    setTargetAudience(option.target_audience);
    setTone(option.tone);
    setDisclaimer(option.disclaimer);
    setAssetIdsText("");
    setLogoAssetId("");
    resetRenderState();
  }, [cleanup, resetRenderState, selectedTemplate]);

  const refreshProject = useCallback(async (projectId: string) => {
    const refreshed = await getStudioProject(projectId);
    if (!mounted.current) return null;
    setProject(refreshed);
    return refreshed;
  }, []);

  const pollGeneration = useCallback(
    (projectId: string, generationId: string) => {
      const tick = async () => {
        if (!mounted.current) return;
        abort.current = new AbortController();
        try {
          const res = await getGenerationStatus(generationId, abort.current.signal);
          if (!mounted.current) return;
          setGenerationStatus(res.status);
          if (TERMINAL.has(res.status)) {
            const refreshed = await refreshProject(projectId);
            if (!mounted.current) return;
            setPhase(res.status === "SUCCEEDED" ? "done" : "error");
            if (res.status !== "SUCCEEDED") {
              setErrorMsg(res.error_code ? messageForErrorCode(res.error_code) : "렌더가 완료되지 못했어요.");
            }
            if (res.status === "SUCCEEDED" && refreshed?.output_asset_id) {
              setErrorMsg(null);
            }
            return;
          }
          timer.current = setTimeout(tick, 1200);
        } catch (err) {
          if (!mounted.current) return;
          setApiError(err);
        }
      };
      void tick();
    },
    [refreshProject, setApiError],
  );

  const handleCreateDraft = useCallback(async () => {
    cleanup();
    setErrorMsg(null);
    setGenerationStatus(null);
    setPhase("drafting");
    renderKey.current = null;
    try {
      const assetIds = parseAssetIds(assetIdsText);
      const logoId = toNullable(logoAssetId);
      if (hasInvalidAssetReference(assetIds, logoId)) {
        setErrorMsg("asset_id는 등록된 ID만 입력할 수 있어요.");
        setPhase("idle");
        return;
      }
      const created = await createStudioProject({
        template_type: selectedTemplate,
        category,
        title: title.trim(),
        offer_text: offerText.trim(),
        cta_text: ctaText.trim(),
        duration_seconds: durationSeconds,
        target_audience: toNullable(targetAudience),
        tone,
        asset_ids: assetIds,
        logo_asset_id: logoId,
        disclaimer: toNullable(disclaimer),
      });
      const drafted = await createStudioDraft(created.project_id);
      if (!mounted.current) return;
      setProject(drafted);
      setPhase("editing");
    } catch (err) {
      if (!mounted.current) return;
      setApiError(err);
    }
  }, [
    assetIdsText,
    category,
    cleanup,
    ctaText,
    disclaimer,
    durationSeconds,
    logoAssetId,
    offerText,
    selectedTemplate,
    setApiError,
    targetAudience,
    title,
    tone,
  ]);

  const handleRender = useCallback(async () => {
    if (!project?.draft) return;
    cleanup();
    setErrorMsg(null);
    setPhase("rendering");
    try {
      const saved = await updateStudioDraft(project.project_id, {
        script: project.draft.script,
        storyboard: project.draft.storyboard,
      });
      if (!mounted.current) return;
      setProject(saved);
      const key = renderKey.current ?? crypto.randomUUID();
      renderKey.current = key;
      const render = await renderStudioProject(saved.project_id, key);
      if (!mounted.current) return;
      setGenerationStatus(render.status);
      setProject((prev) =>
        prev?.project_id === saved.project_id
          ? {
              ...prev,
              status: "RENDERING",
              render_generation_id: render.generation_id,
              render_status: render.status,
            }
          : prev,
      );
      pollGeneration(saved.project_id, render.generation_id);
    } catch (err) {
      if (!mounted.current) return;
      setApiError(err);
    }
  }, [cleanup, pollGeneration, project, setApiError]);

  const updateHook = useCallback((value: string) => {
    setProject((prev) =>
      prev?.draft
        ? { ...prev, draft: { ...prev.draft, script: { ...prev.draft.script, hook: value } } }
        : prev,
    );
  }, []);

  const updateCta = useCallback((value: string) => {
    setProject((prev) =>
      prev?.draft
        ? { ...prev, draft: { ...prev.draft, script: { ...prev.draft.script, cta: value } } }
        : prev,
    );
  }, []);

  const updateNarration = useCallback((index: number, value: string) => {
    setProject((prev) => {
      if (!prev?.draft) return prev;
      return {
        ...prev,
        draft: {
          ...prev.draft,
          script: {
            ...prev.draft.script,
            narration: prev.draft.script.narration.map((line, i) => (i === index ? value : line)),
          },
        },
      };
    });
  }, []);

  const updateSceneCaption = useCallback((sceneIndex: number, value: string) => {
    setProject((prev) => {
      if (!prev?.draft) return prev;
      return {
        ...prev,
        draft: {
          ...prev.draft,
          storyboard: prev.draft.storyboard.map((scene) =>
            scene.scene_index === sceneIndex ? { ...scene, caption: value } : scene,
          ),
        },
      };
    });
  }, []);

  const updateScenePrompt = useCallback((sceneIndex: number, value: string) => {
    setProject((prev) => {
      if (!prev?.draft) return prev;
      return {
        ...prev,
        draft: {
          ...prev.draft,
          storyboard: prev.draft.storyboard.map((scene) =>
            scene.scene_index === sceneIndex ? { ...scene, visual_prompt: value } : scene,
          ),
        },
      };
    });
  }, []);

  const currentAssetIds = parseAssetIds(assetIdsText);
  const currentLogoAssetId = toNullable(logoAssetId);
  const assetReferenceError = hasInvalidAssetReference(currentAssetIds, currentLogoAssetId);
  const canDraft = Boolean(title.trim() && offerText.trim() && ctaText.trim() && !assetReferenceError);
  const busy = phase === "drafting" || phase === "rendering";
  const activeStep = resolveFlowStep(phase, project);
  const activeStepIndex = flowSteps.findIndex((step) => step.id === activeStep);
  const activeStepLabel = flowSteps.find((step) => step.id === activeStep)?.label ?? "Template";
  const renderStatus = generationStatus ?? project?.render_status ?? null;
  const selectedTemplateOption = getTemplateOption(selectedTemplate);
  const hasResult = phase === "done" || (phase === "error" && Boolean(project?.render_generation_id));
  const draftLocked = busy || Boolean(project?.render_generation_id);
  const inputLocked = busy || Boolean(project);
  const storyboardDuration = project?.draft?.storyboard.reduce(
    (total, scene) => total + scene.duration_seconds,
    0,
  );

  return (
    <div className="min-h-dvh bg-[var(--ui-surface-page)]">
      <div className="mx-auto grid w-full max-w-7xl gap-5 px-4 py-4 sm:px-6 lg:grid-cols-[220px_minmax(0,1fr)_360px] lg:px-8">
        <aside className="hidden min-h-[calc(100dvh-2rem)] rounded-lg bg-[var(--ui-surface-inverse)] p-4 text-[var(--ui-content-inverse)] lg:flex lg:flex-col">
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
          <div className="mt-8 border-t studio-inverse-divider pt-4 text-sm">
            <p className="font-semibold">Local AI route</p>
            <ol className="mt-3 flex flex-col gap-2 text-xs text-[var(--ui-content-inverse-muted)]">
              {serverRoute.map((step, index) => (
                <li key={step} className="flex items-center gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--ui-border-inverse)] font-mono text-[10px]">
                    {index + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>
          <div className="mt-auto rounded-lg border studio-inverse-divider p-3 text-xs text-[var(--ui-content-inverse-muted)]">
            <p className="font-semibold text-[var(--ui-content-inverse)]">Boundary</p>
            <p className="mt-2">FE는 Provider, key, image URL을 직접 다루지 않습니다.</p>
          </div>
        </aside>

        <section className="flex min-w-0 flex-col gap-5">
          <header className="studio-panel-elevated overflow-hidden">
            <div className="p-4 sm:p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-[var(--ui-action-accent)]">
                    Studio · Mock-first
                  </p>
                  <h1 className="mt-2 text-3xl font-bold sm:text-4xl">{templateLabels[selectedTemplate]}</h1>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--ui-content-secondary)]">
                    Salon용 9:16 쇼츠를 프로젝트 단위로 만들고, script와 storyboard를 확인한 뒤 렌더합니다.
                  </p>
                </div>
                {project && (
                  <Button type="button" variant="secondary" onClick={handleStartOver} disabled={busy}>
                    새 작업
                  </Button>
                )}
              </div>

              <ol className="mt-5 grid gap-2 sm:grid-cols-4">
                {flowSteps.map((step, index) => {
                  const isCurrent = step.id === activeStep;
                  const isDone = index < activeStepIndex;
                  return (
                    <li
                      key={step.id}
                      className={`min-h-[72px] rounded-lg border px-3 py-2 ${
                        isCurrent
                          ? "border-[var(--ui-action-primary)] bg-[var(--ui-action-primary)] text-[var(--ui-action-on-primary)]"
                          : isDone
                            ? "border-[var(--ui-status-success-bg)] bg-[var(--ui-status-success-bg)] text-[var(--ui-status-success-text)]"
                            : "border-[var(--ui-border-default)] bg-[var(--ui-surface-elevated)] text-[var(--ui-content-muted)]"
                      }`}
                      aria-current={isCurrent ? "step" : undefined}
                    >
                      <span className="font-mono text-xs">{String(index + 1).padStart(2, "0")}</span>
                      <span className="mt-1 block text-sm font-bold">{step.label}</span>
                      <span className="mt-0.5 block text-xs opacity-80">{step.detail}</span>
                    </li>
                  );
                })}
              </ol>
            </div>
          </header>

          <StudioSection
            eyebrow="Templates"
            title="제작 유형"
            body={selectedTemplateOption.summary}
            action={<span className="studio-pill px-3 py-1 text-xs font-semibold">{activeStepLabel}</span>}
          >
            <fieldset className="mt-4">
              <legend className="sr-only">Studio template</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                {templateOptions.map((option) => {
                  const selected = selectedTemplate === option.template_type;
                  return (
                    <button
                      key={option.template_type}
                      type="button"
                      onClick={() => handleSelectTemplate(option.template_type)}
                      disabled={busy}
                      aria-pressed={selected}
                      className={`min-h-[144px] rounded-lg border p-4 text-left transition-colors disabled:opacity-60 ${
                        selected
                          ? "border-[var(--ui-action-primary)] bg-[var(--ui-action-primary)] text-[var(--ui-action-on-primary)]"
                          : "border-[var(--ui-border-default)] bg-[var(--ui-surface-elevated)] text-[var(--ui-content-primary)] hover:border-[var(--ui-border-strong)]"
                      }`}
                    >
                      <span
                        className={`text-xs font-semibold ${
                          selected ? "text-[var(--ui-content-inverse-muted)]" : "text-[var(--ui-action-accent)]"
                        }`}
                      >
                        {templateLabels[option.template_type]}
                      </span>
                      <span className="mt-2 block text-lg font-bold">{option.title}</span>
                      <span
                        className={`mt-2 block text-sm leading-6 ${
                          selected ? "text-[var(--ui-content-inverse-muted)]" : "text-[var(--ui-content-secondary)]"
                        }`}
                      >
                        {option.summary}
                      </span>
                      <span
                        className={`mt-3 block text-xs ${
                          selected ? "text-[var(--ui-content-inverse-muted)]" : "text-[var(--ui-content-muted)]"
                        }`}
                      >
                        {categoryLabels[option.category]} · {option.duration_seconds}초 · {toneLabels[option.tone]}
                      </span>
                    </button>
                  );
                })}
              </div>
            </fieldset>
          </StudioSection>

          <StudioSection
            eyebrow="Brief"
            title="쇼츠 입력"
            body="게시 전 검토할 제목, 혜택, CTA와 안전한 asset_id 참조만 보냅니다."
            action={
              project ? (
                <span className="studio-pill break-all px-3 py-1 font-mono text-xs">{project.project_id}</span>
              ) : null
            }
          >
            <fieldset className="mt-4">
              <legend className="studio-label">카테고리</legend>
              <div className="mt-2 grid grid-cols-2 overflow-hidden rounded-lg border border-[var(--ui-border-default)] sm:grid-cols-5">
                {(["HAIR", "BEAUTY", "HEALTH", "PRODUCT", "LOCAL_BUSINESS"] as const).map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => setCategory(item)}
                    disabled={inputLocked}
                    aria-pressed={category === item}
                    className={`min-h-11 text-xs font-semibold sm:text-sm ${
                      category === item
                        ? "bg-[var(--ui-action-primary)] text-[var(--ui-action-on-primary)]"
                        : "bg-[var(--ui-surface-elevated)] text-[var(--ui-content-secondary)]"
                    }`}
                  >
                    {categoryLabels[item]}
                  </button>
                ))}
              </div>
            </fieldset>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Field label="제목">
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  disabled={inputLocked}
                  className="studio-input px-3 text-base disabled:opacity-60"
                />
              </Field>
              <Field label="CTA">
                <input
                  value={ctaText}
                  onChange={(e) => setCtaText(e.target.value)}
                  disabled={inputLocked}
                  className="studio-input px-3 text-base disabled:opacity-60"
                />
              </Field>
            </div>

            <div className="mt-4">
              <Field label="혜택·가격·기간">
                <textarea
                  value={offerText}
                  onChange={(e) => setOfferText(e.target.value)}
                  rows={3}
                  disabled={inputLocked}
                  className="studio-input min-h-[108px] resize-none p-3 text-base disabled:opacity-60"
                />
              </Field>
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Field label="대상">
                <input
                  value={targetAudience}
                  onChange={(e) => setTargetAudience(e.target.value)}
                  disabled={inputLocked}
                  className="studio-input px-3 text-base disabled:opacity-60"
                />
              </Field>
              <Field label="안내 문구">
                <input
                  value={disclaimer}
                  onChange={(e) => setDisclaimer(e.target.value)}
                  disabled={inputLocked}
                  className="studio-input px-3 text-base disabled:opacity-60"
                />
              </Field>
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <fieldset>
                <legend className="studio-label">길이</legend>
                <div className="mt-2 grid grid-cols-2 overflow-hidden rounded-lg border border-[var(--ui-border-default)]">
                  {[15, 30].map((seconds) => (
                    <button
                      key={seconds}
                      type="button"
                      onClick={() => setDurationSeconds(seconds as 15 | 30)}
                      disabled={inputLocked}
                      aria-pressed={durationSeconds === seconds}
                      className={`min-h-11 text-sm font-semibold ${
                        durationSeconds === seconds
                          ? "bg-[var(--ui-action-primary)] text-[var(--ui-action-on-primary)]"
                          : "bg-[var(--ui-surface-elevated)] text-[var(--ui-content-secondary)]"
                      }`}
                    >
                      {seconds}초
                    </button>
                  ))}
                </div>
              </fieldset>
              <fieldset>
                <legend className="studio-label">톤</legend>
                <div className="mt-2 grid grid-cols-2 overflow-hidden rounded-lg border border-[var(--ui-border-default)] sm:grid-cols-4">
                  {(["FRIENDLY", "TRENDY", "PREMIUM", "CALM"] as const).map((item) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => setTone(item)}
                      disabled={inputLocked}
                      aria-pressed={tone === item}
                      className={`min-h-11 text-xs font-semibold sm:text-sm ${
                        tone === item
                          ? "bg-[var(--ui-action-primary)] text-[var(--ui-action-on-primary)]"
                          : "bg-[var(--ui-surface-elevated)] text-[var(--ui-content-secondary)]"
                      }`}
                    >
                      {toneLabels[item]}
                    </button>
                  ))}
                </div>
              </fieldset>
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Field label="이미지 asset_id" hint="최대 6개, 쉼표 구분. URL·path·Base64는 거부됩니다.">
                <input
                  value={assetIdsText}
                  onChange={(e) => setAssetIdsText(e.target.value)}
                  disabled={inputLocked}
                  placeholder="asset-1, asset-2"
                  className="studio-input px-3 text-base disabled:opacity-60"
                />
              </Field>
              <Field label="로고 asset_id" hint="선택 입력">
                <input
                  value={logoAssetId}
                  onChange={(e) => setLogoAssetId(e.target.value)}
                  disabled={inputLocked}
                  className="studio-input px-3 text-base disabled:opacity-60"
                />
              </Field>
            </div>
            {assetReferenceError && (
              <p
                className="mt-3 rounded-lg bg-[var(--ui-status-error-bg)] px-3 py-2 text-sm text-[var(--ui-status-error-text)]"
                role="alert"
              >
                asset_id는 등록된 ID만 입력할 수 있어요.
              </p>
            )}

            <Button
              className="mt-5 w-full sm:w-auto"
              onClick={handleCreateDraft}
              disabled={!canDraft || busy || Boolean(project)}
              aria-busy={phase === "drafting"}
            >
              {phase === "drafting" ? "초안 생성 중..." : "Draft 생성"}
            </Button>
          </StudioSection>

          {project?.draft && (
            <StudioSection
              eyebrow="Draft"
              title="Script & Storyboard"
              body="렌더 전에 hook, narration, scene caption과 visual prompt를 확정합니다."
              action={<span className="studio-pill px-3 py-1 font-mono text-xs">v{project.draft.version}</span>}
            >
              <div className="mt-4 grid gap-4">
                <Field label="Hook">
                  <textarea
                    value={project.draft.script.hook}
                    onChange={(e) => updateHook(e.target.value)}
                    disabled={draftLocked}
                    rows={2}
                    className="studio-input min-h-[88px] resize-none p-3 text-base disabled:opacity-60"
                  />
                </Field>
                <div className="grid gap-3">
                  {project.draft.script.narration.map((line, index) => (
                    <Field key={`${project.project_id}-narration-${index}`} label={`Narration ${index + 1}`}>
                      <textarea
                        value={line}
                        onChange={(e) => updateNarration(index, e.target.value)}
                        disabled={draftLocked}
                        rows={2}
                        className="studio-input min-h-[88px] resize-none p-3 text-base disabled:opacity-60"
                      />
                    </Field>
                  ))}
                </div>
                <Field label="CTA">
                  <input
                    value={project.draft.script.cta}
                    onChange={(e) => updateCta(e.target.value)}
                    disabled={draftLocked}
                    className="studio-input px-3 text-base disabled:opacity-60"
                  />
                </Field>
              </div>

              <div className="mt-6 divide-y divide-[var(--ui-border-default)]">
                {project.draft.storyboard.map((scene) => (
                  <div key={scene.scene_index} className="grid gap-3 py-4 sm:grid-cols-[96px_minmax(0,1fr)]">
                    <div>
                      <p className="text-sm font-bold text-[var(--ui-content-primary)]">
                        Scene {scene.scene_index}
                      </p>
                      <p className="mt-1 font-mono text-xs text-[var(--ui-content-muted)]">
                        {scene.duration_seconds}s
                      </p>
                    </div>
                    <div className="grid gap-3">
                      <input
                        value={scene.caption}
                        onChange={(e) => updateSceneCaption(scene.scene_index, e.target.value)}
                        disabled={draftLocked}
                        className="studio-input px-3 text-base disabled:opacity-60"
                      />
                      <textarea
                        value={scene.visual_prompt}
                        onChange={(e) => updateScenePrompt(scene.scene_index, e.target.value)}
                        disabled={draftLocked}
                        rows={2}
                        className="studio-input min-h-[88px] resize-none p-3 text-base disabled:opacity-60"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </StudioSection>
          )}

          {project?.draft && (
            <StudioSection
              eyebrow="Render"
              title="생성 작업"
              body="현재는 Mock 또는 명시 opt-in된 backend-only 로컬 Provider만 사용합니다."
              action={
                renderStatus ? (
                  <StatusBadge status={renderStatus} showSpinner={phase === "rendering"} />
                ) : (
                  <span className="studio-pill px-3 py-1 text-xs font-semibold">Ready</span>
                )
              }
            >
              <div className="mt-4 divide-y divide-[var(--ui-border-default)]">
                <DetailRow label="Output" value={`${project.duration_seconds}s · 9:16`} />
                <DetailRow label="Template" value={templateLabels[project.template_type]} />
                <DetailRow label="Scenes" value={`${project.draft.storyboard.length}개 · ${storyboardDuration ?? 0}s`} />
                <DetailRow
                  label="Storage"
                  value={`${project.storage.backend} · ${project.storage.output_retention_days}d`}
                />
              </div>
              <Button
                className="mt-5 w-full sm:w-auto"
                onClick={handleRender}
                disabled={busy || Boolean(project.render_generation_id)}
                aria-busy={phase === "rendering"}
              >
                {phase === "rendering" ? "렌더 진행 중..." : "Render 시작"}
              </Button>
            </StudioSection>
          )}

          {project?.render_generation_id && (
            <StudioSection
              eyebrow="Result"
              title="결과 참조"
              body="공개 URL이 아니라 서버 내부 asset 참조만 표시합니다."
              action={renderStatus ? <StatusBadge status={renderStatus} showSpinner={phase === "rendering"} /> : null}
            >
              <div className="mt-4 divide-y divide-[var(--ui-border-default)]">
                <DetailRow label="generation_id" value={project.render_generation_id} mono />
                <DetailRow label="output_asset_id" value={project.output_asset_id ?? "대기 중"} mono />
              </div>

              {hasResult && project.output_asset_id && (
                <p className="mt-4 rounded-lg bg-[var(--ui-status-success-bg)] px-3 py-2 text-sm font-medium text-[var(--ui-status-success-text)]">
                  Mock 결과 asset 참조가 생성되었습니다.
                </p>
              )}
              {phase === "error" && (
                <p
                  className="mt-4 rounded-lg bg-[var(--ui-status-error-bg)] px-3 py-2 text-sm text-[var(--ui-status-error-text)]"
                  role="alert"
                >
                  {errorMsg ?? "렌더 결과를 만들지 못했어요."}
                </p>
              )}

              <div className="mt-4 grid grid-cols-3 gap-2">
                {["Preview", "Download", "QR"].map((action) => (
                  <button
                    key={action}
                    type="button"
                    disabled
                    className="min-h-11 rounded-lg border border-[var(--ui-border-default)] bg-[var(--ui-surface-muted)] text-xs font-semibold text-[var(--ui-content-muted)]"
                  >
                    {action}
                  </button>
                ))}
              </div>
            </StudioSection>
          )}
        </section>

        <aside className="lg:sticky lg:top-4 lg:self-start">
          <section className="studio-preview-frame rounded-lg p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-base font-bold">9:16 Preview</h2>
              {renderStatus && <StatusBadge status={renderStatus} showSpinner={phase === "rendering"} />}
            </div>

            <AspectRatioMedia className="mt-4">
              <div className="studio-preview-canvas flex h-full w-full flex-col justify-between p-5 text-[var(--ui-content-inverse)]">
                <div className="flex items-center justify-between text-[11px] text-[var(--ui-content-inverse-muted)]">
                  <span>{categoryLabels[project?.category ?? category]}</span>
                  <span>{durationSeconds}s</span>
                </div>
                <div>
                  <p className="text-2xl font-bold leading-tight">{project?.title ?? title}</p>
                  <p className="mt-3 text-sm leading-6 text-[var(--ui-content-inverse-muted)]">
                    {project?.draft?.script.hook ?? selectedTemplateOption.summary}
                  </p>
                </div>
                <div className="grid gap-2 text-xs">
                  {(project?.draft?.storyboard.slice(0, 3) ?? []).map((scene) => (
                    <span key={scene.scene_index} className="rounded bg-[var(--ui-border-inverse)] px-2 py-1">
                      {String(scene.scene_index).padStart(2, "0")} · {scene.caption}
                    </span>
                  ))}
                  {!project?.draft && (
                    <>
                      <span className="rounded bg-[var(--ui-border-inverse)] px-2 py-1">01 · Hook</span>
                      <span className="rounded bg-[var(--ui-border-inverse)] px-2 py-1">02 · Offer</span>
                      <span className="rounded bg-[var(--ui-border-inverse)] px-2 py-1">03 · Booking</span>
                    </>
                  )}
                </div>
              </div>
            </AspectRatioMedia>

            <div className="mt-4 divide-y studio-inverse-divider text-sm">
              <div className="flex justify-between gap-3 py-2">
                <span className="text-[var(--ui-content-inverse-muted)]">Step</span>
                <span className="font-semibold">{activeStepLabel}</span>
              </div>
              <div className="flex justify-between gap-3 py-2">
                <span className="text-[var(--ui-content-inverse-muted)]">Template</span>
                <span className="font-semibold">{templateLabels[selectedTemplate]}</span>
              </div>
              <div className="flex justify-between gap-3 py-2">
                <span className="text-[var(--ui-content-inverse-muted)]">Provider</span>
                <span className="font-semibold">backend-only</span>
              </div>
              <div className="flex justify-between gap-3 py-2">
                <span className="text-[var(--ui-content-inverse-muted)]">Storage</span>
                <span className="font-mono text-xs">
                  {project?.storage.storage_profile_name ?? "local-dev"}
                </span>
              </div>
            </div>

            {project?.output_asset_id && (
              <p className="mt-4 break-all font-mono text-xs text-[var(--ui-content-inverse-muted)]">
                output_asset_id: {project.output_asset_id}
              </p>
            )}

            {errorMsg && phase !== "error" && (
              <p
                className="mt-4 rounded-lg bg-[var(--ui-status-error-bg)] px-3 py-2 text-sm text-[var(--ui-status-error-text)]"
                role="alert"
              >
                {errorMsg}
              </p>
            )}

            <p className="mt-4 text-xs leading-5 text-[var(--ui-content-inverse-muted)]" role="status" aria-live="polite">
              AI 초안은 게시 전 매장 조건과 안내 문구를 확인해야 합니다.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
