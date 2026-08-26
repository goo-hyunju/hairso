"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createVideoGeneration, getGenerationStatus } from "@/lib/api/generations";
import { ApiError, messageForErrorCode } from "@/lib/api/errors";
import type { GenerationStatus } from "@/types/generation";
import { AspectRatioMedia } from "@/components/AspectRatioMedia";
import { Button } from "@/components/Button";
import { StatusBadge } from "@/components/StatusBadge";

/**
 * 상담→생성 데모 화면(카메라 없이 동작). Mock 백엔드에 실제로 붙는다:
 *   프롬프트 → POST /video-generations(202) → GET /generations/{id} 폴링 → 상태 Mapper 표시 → 완료.
 * 실 이미지·영상 생성과 카메라 촬영은 로드맵.
 */

const TERMINAL: ReadonlySet<GenerationStatus> = new Set<GenerationStatus>([
  "SUCCEEDED",
  "FAILED",
  "CANCELED",
  "EXPIRED",
]);

type Phase = "idle" | "running" | "done" | "error";

function isAbortError(err: unknown): boolean {
  return (
    typeof err === "object" &&
    err !== null &&
    "name" in err &&
    (err as { name: unknown }).name === "AbortError"
  );
}

export function GenerationFlow() {
  const [prompt, setPrompt] = useState(
    "정면에서 35도로 천천히 고개를 돌리고, 머리끝만 가볍게 흔들리게 해주세요.",
  );
  const [phase, setPhase] = useState<Phase>("idle");
  const [status, setStatus] = useState<GenerationStatus | null>(null);
  const [genId, setGenId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mounted = useRef(true);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abort = useRef<AbortController | null>(null);

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

  const poll = useCallback((id: string) => {
    const tick = async () => {
      if (!mounted.current) return;
      abort.current = new AbortController();
      try {
        const res = await getGenerationStatus(id, abort.current.signal);
        if (!mounted.current) return;
        setStatus(res.status);
        if (TERMINAL.has(res.status)) {
          setPhase(res.status === "SUCCEEDED" ? "done" : "error");
          if (res.status !== "SUCCEEDED" && res.error_code) {
            setErrorMsg("생성이 완료되지 못했어요. 다시 시도해 주세요.");
          }
          return;
        }
        timer.current = setTimeout(tick, 1200);
      } catch (err) {
        if (!mounted.current) return;
        if (isAbortError(err)) return;
        const code = err instanceof ApiError ? err.code : "UNKNOWN";
        setErrorMsg(messageForErrorCode(code));
        setPhase("error");
      }
    };
    void tick();
  }, []);

  const onGenerate = useCallback(async () => {
    cleanup();
    setErrorMsg(null);
    setStatus(null);
    setGenId(null);
    setPhase("running");
    try {
      const res = await createVideoGeneration({
        consultation_id: "demo-consultation",
        image_asset_id: "demo-face-asset", // 실제로는 업로드된 asset id (로드맵)
        prompt: prompt.trim() || "turn head slowly",
        duration_seconds: 5,
        aspect_ratio: "9:16",
        quality: "720p",
        idempotency_key: crypto.randomUUID(),
      });
      if (!mounted.current) return;
      setGenId(res.generation_id);
      setStatus(res.status);
      poll(res.generation_id);
    } catch (err) {
      if (!mounted.current) return;
      if (isAbortError(err)) return;
      const code = err instanceof ApiError ? err.code : "UNKNOWN";
      setErrorMsg(messageForErrorCode(code));
      setPhase("error");
    }
  }, [prompt, poll, cleanup]);

  const busy = phase === "running";

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-5">
      <div className="flex flex-col gap-2">
        <label htmlFor="prompt" className="studio-label">
          어떤 움직임의 영상으로 만들까요?
        </label>
        <textarea
          id="prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          disabled={busy}
          className="studio-input min-h-[108px] resize-none p-3 text-base disabled:opacity-60"
        />
      </div>

      <Button onClick={onGenerate} disabled={busy} aria-busy={busy}>
        {busy ? "생성 중…" : phase === "done" || phase === "error" ? "다시 생성" : "영상 생성"}
      </Button>

      {status && <StatusBadge status={status} showSpinner={busy} className="self-start" />}

      {errorMsg && (
        <p
          className="rounded-lg bg-[var(--ui-status-error-bg)] px-4 py-3 text-sm text-[var(--ui-status-error-text)]"
          role="alert"
        >
          {errorMsg}
        </p>
      )}

      {phase === "done" && (
        <div className="flex flex-col gap-2">
          <AspectRatioMedia className="mx-auto max-w-[220px]">
            <div className="flex h-full w-full items-center justify-center bg-[var(--ui-action-accent-soft)] text-center text-sm text-[var(--ui-action-accent)]">
              완료된 5초 영상 자리
              <br />
              (실 영상 생성은 로드맵)
            </div>
          </AspectRatioMedia>
          <p className="text-center text-xs text-[var(--ui-content-muted)]">
            AI 예상 결과입니다. 실제 시술 결과는 모질·두상 등에 따라 달라질 수 있어요.
          </p>
        </div>
      )}

      {genId && (
        <p className="text-center font-mono text-[11px] text-[var(--ui-content-muted)]">
          generation_id: {genId}
        </p>
      )}
    </div>
  );
}
