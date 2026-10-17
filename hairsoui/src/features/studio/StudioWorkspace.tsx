"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type ChangeEvent, type ReactNode } from "react";
import { AspectRatioMedia } from "@/components/AspectRatioMedia";
import { Button } from "@/components/Button";
import { StatusBadge } from "@/components/StatusBadge";
import { uploadAsset } from "@/lib/api/assets";
import { ApiError, messageForErrorCode } from "@/lib/api/errors";
import { getGenerationStatus } from "@/lib/api/generations";
import {
  createStudioDraft,
  createStudioProject,
  getStudioProjectDownloadPath,
  getStudioProject,
  renderStudioProject,
  updateStudioDraft,
} from "@/lib/api/studio";
import {
  checkFileSize,
  checkMimeType,
  validateImageMeta,
  type ValidationCode,
} from "@/lib/validation/image";
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
  PET: "Pet",
  GENERAL: "General",
};

const studioCategories: StudioCategory[] = [
  "HAIR",
  "BEAUTY",
  "HEALTH",
  "PRODUCT",
  "LOCAL_BUSINESS",
  "PET",
  "GENERAL",
];

const flowSteps = [
  { id: "templates", label: "템플릿", detail: "작업 유형" },
  { id: "draft", label: "초안", detail: "대본·씬" },
  { id: "render", label: "렌더", detail: "생성 작업" },
  { id: "result", label: "결과", detail: "결과 참조" },
] as const;

const templateLabels: Record<StudioTemplateType, string> = {
  HAIR_STYLING_MOTION: "헤어 연출",
  PROMOTION_SHORT: "매장 안내",
  SALON_EVENT_PROMOTION: "일정 안내",
  FREE_IMAGE_TO_VIDEO: "프롬프트 영상",
};

interface StudioTemplateOption {
  id: string;
  template_type: StudioTemplateType;
  label: string;
  category: StudioCategory;
  title: string;
  summary: string;
  detail: string;
  duration_seconds: StudioDurationSeconds;
  offer_text: string;
  cta_text: string;
  target_audience: string;
  tone: StudioTone;
  disclaimer: string;
}

type StudioDurationSeconds = 5 | 15 | 30;

const FREE_PROMPT_OPTION_ID = "free-custom-prompt";
const FREE_PROMPT_PROJECT_TITLE = "자유 영상";
const FREE_PROMPT_PROJECT_CTA = "영상 생성";
const durationOptions: StudioDurationSeconds[] = [5, 15, 30];

const freePromptTemplateOption: StudioTemplateOption = {
  id: FREE_PROMPT_OPTION_ID,
  template_type: "FREE_IMAGE_TO_VIDEO",
  label: "자유 프롬프트",
  category: "GENERAL",
  title: "자유 영상",
  summary: "주제 제한 없이 업로드 이미지와 직접 입력한 프롬프트로 짧은 영상을 만듭니다.",
  detail: "인물, 공간, 제품, 음식, 풍경 등 원하는 사진을 기준으로 움직임과 분위기를 직접 지시할 수 있습니다.",
  duration_seconds: 5,
  offer_text: "",
  cta_text: "",
  target_audience: "자유 영상",
  tone: "CALM",
  disclaimer: "원본의 주요 피사체, 색감, 배경 구조를 유지합니다.",
};

const hairStylingTemplateOption: StudioTemplateOption = {
  id: "hair-natural-flow",
  template_type: "HAIR_STYLING_MOTION",
  label: "자연 흐름",
  category: "HAIR",
  title: "자연스러운 헤어 스타일링",
  summary: "업로드 사진의 헤어 라인, 결, 움직임을 자연스럽게 살려 짧은 연출 클립을 만듭니다.",
  detail: "얼굴과 기존 헤어 구조를 유지하면서 부드러운 고개 움직임, 미세한 모발 흔들림, 자연광에 가까운 톤을 만듭니다.",
  duration_seconds: 5,
  offer_text:
    "장면: 업로드한 사진 속 인물과 현재 헤어스타일 그대로\n동작: 고개를 살짝 돌리면 머릿결이 부드럽고 자연스럽게 흔들림\n카메라: 고정, 아주 느린 줌인\n스타일: realistic, natural salon lighting\n금지사항: 화면에 텍스트 넣지 말 것, 얼굴 왜곡 없게, 헤어 컷과 컬러는 그대로 유지",
  cta_text: "자연스러운 헤어 연출",
  target_audience: "자연스러운 헤어 연출",
  tone: "CALM",
  disclaimer: "얼굴, 헤어 라인, 기존 모발 색은 유지합니다.",
};

const defaultTemplateOption: StudioTemplateOption = hairStylingTemplateOption;

const templateOptions: StudioTemplateOption[] = [
  freePromptTemplateOption,
  {
    id: "portrait-subtle-motion",
    template_type: "FREE_IMAGE_TO_VIDEO",
    label: "인물 모션",
    category: "GENERAL",
    title: "인물 자연 모션",
    summary: "인물 사진에 자연스러운 시선, 표정, 카메라 움직임을 더합니다.",
    detail: "얼굴 정체성과 전체 분위기를 유지하면서 과하지 않은 움직임을 만드는 범용 인물 프리셋입니다.",
    duration_seconds: 5,
    offer_text:
      "장면: 업로드한 인물 사진의 분위기와 배경 그대로\n동작: 시선이 천천히 움직이고 고개를 살짝 돌리며 자연스러운 표정 변화\n카메라: 고정, 미세한 줌인\n스타일: realistic, cinematic\n금지사항: 텍스트 넣지 말 것, 얼굴 왜곡 없게, 인물 정체성 유지",
    cta_text: "인물 모션",
    target_audience: "인물 영상",
    tone: "CALM",
    disclaimer: "얼굴 정체성, 표정 분위기, 배경 구조를 유지합니다.",
  },
  {
    id: "food-natural-motion",
    template_type: "FREE_IMAGE_TO_VIDEO",
    label: "음식 모션",
    category: "GENERAL",
    title: "음식 자연 모션",
    summary: "음식 사진에 김, 소스, 카메라 이동 같은 작은 움직임을 더합니다.",
    detail: "접시 구성과 재료 형태를 유지하면서 음식이 더 생생해 보이도록 짧은 움직임을 만듭니다.",
    duration_seconds: 5,
    offer_text:
      "장면: 업로드한 음식 사진의 접시 구성 그대로\n동작: 김이 살짝 피어오르고 소스가 천천히 흐르는 정도의 작은 움직임\n카메라: 느린 줌인\n스타일: realistic, appetizing lighting\n금지사항: 텍스트 넣지 말 것, 접시 구성과 음식 형태 유지",
    cta_text: "음식 모션",
    target_audience: "음식 영상",
    tone: "FRIENDLY",
    disclaimer: "음식 형태, 접시 구성, 배경은 원본 기준을 유지합니다.",
  },
  hairStylingTemplateOption,
  {
    id: "hair-cut-shape",
    template_type: "HAIR_STYLING_MOTION",
    label: "컷 라인",
    category: "HAIR",
    title: "컷 라인 입체 연출",
    summary: "레이어, 볼륨, 앞머리 라인이 보이도록 머리 형태를 짧게 보여줍니다.",
    detail: "정면 사진을 기준으로 살짝 옆을 보는 움직임을 넣어 컷 라인의 깊이와 볼륨을 확인하기 쉽게 만듭니다.",
    duration_seconds: 5,
    offer_text:
      "장면: 정면 인물 사진 기준, 컷 라인과 레이어가 잘 보이게\n동작: 고개를 천천히 옆으로 돌려 컷의 형태와 볼륨이 드러남\n카메라: 고정\n스타일: realistic, natural hair texture\n금지사항: 텍스트 넣지 말 것, 얼굴형과 헤어 라인 과장 없게",
    cta_text: "컷 라인 미리보기",
    target_audience: "컷 라인 확인",
    tone: "CALM",
    disclaimer: "얼굴형과 헤어 라인은 과장하지 않습니다.",
  },
  {
    id: "hair-gloss-texture",
    template_type: "HAIR_STYLING_MOTION",
    label: "결감 클로즈업",
    category: "HAIR",
    title: "모발 결감 클로즈업",
    summary: "윤기, 결, 컬의 흐름이 자연스럽게 보이는 헤어 디테일 클립입니다.",
    detail: "카메라가 천천히 가까워지는 느낌으로 모발 표면의 결감과 컬 움직임을 강조합니다.",
    duration_seconds: 5,
    offer_text:
      "장면: 모발의 윤기와 결이 잘 보이는 클로즈업\n동작: 머리카락 가닥이 부드럽게 흔들리며 자연스러운 윤기 반사\n카메라: 천천히 가까워지는 줌인\n스타일: realistic, premium salon lighting\n금지사항: 텍스트 넣지 말 것, 모발 색과 길이는 원본 유지",
    cta_text: "모발 결감 보기",
    target_audience: "모발 결감 확인",
    tone: "PREMIUM",
    disclaimer: "모발 색과 길이는 원본 기준을 유지합니다.",
  },
  {
    id: "hair-color-tone",
    template_type: "HAIR_STYLING_MOTION",
    label: "컬러 톤",
    category: "HAIR",
    title: "컬러 톤 자연광 연출",
    summary: "염색 톤과 명암이 과장되지 않도록 자연스러운 빛 움직임을 더합니다.",
    detail: "빛이 살짝 이동하는 연출로 컬러의 깊이와 반사감을 보여주되, 원본 색을 임의로 바꾸지 않습니다.",
    duration_seconds: 5,
    offer_text:
      "장면: 염색 톤이 잘 보이는 인물 사진 그대로\n동작: 빛이 천천히 이동하며 컬러의 깊이와 은은한 하이라이트가 드러남\n카메라: 고정\n스타일: realistic, natural light\n금지사항: 텍스트 넣지 말 것, 원본 컬러보다 밝거나 어둡게 과장하지 말 것",
    cta_text: "컬러 톤 보기",
    target_audience: "컬러 톤 확인",
    tone: "PREMIUM",
    disclaimer: "원본 컬러보다 밝거나 어둡게 과장하지 않습니다.",
  },
  {
    id: "hair-face-line",
    template_type: "HAIR_STYLING_MOTION",
    label: "얼굴선 핏",
    category: "HAIR",
    title: "얼굴선 헤어핏 연출",
    summary: "앞머리, 사이드뱅, 얼굴선 주변의 헤어핏을 자연스럽게 보여줍니다.",
    detail: "미세한 시선 이동과 고개 움직임으로 얼굴선 주변의 헤어 흐름을 확인하기 쉽게 만듭니다.",
    duration_seconds: 5,
    offer_text:
      "장면: 앞머리와 얼굴선 주변 헤어핏이 보이는 인물 사진\n동작: 미세한 시선 이동과 고개 움직임으로 얼굴선 주변 머리 흐름이 살아남\n카메라: 고정\n스타일: realistic, friendly mood\n금지사항: 텍스트 넣지 말 것, 얼굴 비율과 표정 왜곡 없게",
    cta_text: "얼굴선 헤어핏",
    target_audience: "헤어핏 확인",
    tone: "FRIENDLY",
    disclaimer: "얼굴 비율과 표정은 원본 느낌을 유지합니다.",
  },
  {
    id: "salon-style-notice",
    template_type: "PROMOTION_SHORT",
    label: "스타일 안내",
    category: "HAIR",
    title: "스타일링 예약 안내",
    summary: "시술 설명과 예약 안내를 짧은 세로 쇼츠 흐름으로 정리합니다.",
    detail: "매장 소식이나 디자이너 안내가 필요할 때 쓰는 템플릿입니다. 영상 생성 규칙은 BE 뒤에서만 실행됩니다.",
    duration_seconds: 15,
    offer_text: "레이어드 컷과 자연스러운 드라이 스타일 상담 안내",
    cta_text: "예약 가능 시간 확인하기",
    target_audience: "스타일 상담 고객",
    tone: "FRIENDLY",
    disclaimer: "상담 후 모발 상태에 맞춰 진행합니다.",
  },
  {
    id: "salon-booking-notice",
    template_type: "SALON_EVENT_PROMOTION",
    label: "일정 안내",
    category: "LOCAL_BUSINESS",
    title: "주말 예약 오픈 안내",
    summary: "예약 가능한 기간, 매장 분위기, 방문 안내를 30초 흐름으로 구성합니다.",
    detail: "기간이 있는 매장 소식을 설명할 때 사용합니다. 일정, 공간, 분위기 위주로 정리합니다.",
    duration_seconds: 30,
    offer_text: "이번 주말 가능한 스타일 상담과 드라이 연출 안내",
    cta_text: "가능 시간 확인하기",
    target_audience: "근처 방문 고객",
    tone: "TRENDY",
    disclaimer: "이벤트 수량과 시간은 매장 상황에 따라 달라질 수 있습니다.",
  },
  {
    id: "pet-daily-motion",
    template_type: "FREE_IMAGE_TO_VIDEO",
    label: "반려동물 모션",
    category: "PET",
    title: "반려동물 자연 모션",
    summary: "반려동물 사진에 작은 시선, 고개, 몸 움직임을 더합니다.",
    detail: "반려동물의 무늬, 체형, 배경을 유지하면서 자연스러운 작은 동작을 만드는 자유 이미지 영상 템플릿입니다.",
    duration_seconds: 5,
    offer_text:
      "장면: 업로드한 반려동물 사진의 모습과 배경 그대로\n동작: 고개를 살짝 움직이고 몸을 작게 뒤척이는 자연스러운 동작\n카메라: 고정\n스타일: realistic, cozy\n금지사항: 텍스트 넣지 말 것, 무늬·체형·배경 유지",
    cta_text: "편안한 반려동물 순간",
    target_audience: "반려동물 일상 영상",
    tone: "FRIENDLY",
    disclaimer: "반려동물의 무늬, 체형, 배경은 원본 그대로 유지합니다.",
  },
  {
    id: "pet-eating-motion",
    template_type: "FREE_IMAGE_TO_VIDEO",
    label: "밥 먹는 장면",
    category: "PET",
    title: "반려동물이 밥 먹는 장면",
    summary: "반려동물이 그릇 근처에서 자연스럽게 먹는 듯한 짧은 모션을 만듭니다.",
    detail: "반려동물의 무늬, 체형, 주변 배경은 유지하고 고개와 입 주변의 작은 움직임만 더합니다.",
    duration_seconds: 5,
    offer_text:
      "장면: 반려동물이 작은 그릇 앞에 있는 실내\n동작: 그릇에 고개를 숙여 자연스럽게 먹는 작은 움직임\n카메라: 고정\n스타일: realistic, cozy indoor lighting\n금지사항: 텍스트 넣지 말 것, 무늬·그릇·배경 유지",
    cta_text: "밥 먹는 장면",
    target_audience: "반려동물 일상 영상",
    tone: "FRIENDLY",
    disclaimer: "반려동물의 무늬, 그릇, 배경은 원본 그대로 유지합니다.",
  },
  {
    id: "product-clean-motion",
    template_type: "FREE_IMAGE_TO_VIDEO",
    label: "제품 모션",
    category: "PRODUCT",
    title: "제품 클린 모션",
    summary: "제품 사진에 천천히 도는 카메라 움직임과 안정적인 조명을 더합니다.",
    detail: "패키지 형태와 색을 유지하면서 짧은 제품 소개 클립처럼 보이게 만드는 자유 이미지 영상 템플릿입니다.",
    duration_seconds: 5,
    offer_text:
      "장면: 업로드한 제품 사진의 패키지와 배경 그대로\n동작: 제품은 고정된 느낌을 유지하고 조명 반사만 은은하게 변함\n카메라: 제품 주위를 천천히 도는 궤도 이동(orbit)\n스타일: realistic, clean studio lighting\n금지사항: 텍스트 넣지 말 것, 패키지 형태·라벨·색 유지",
    cta_text: "제품 모션",
    target_audience: "제품 소개 영상",
    tone: "PREMIUM",
    disclaimer: "제품 형태, 라벨 위치, 배경은 원본 그대로 유지합니다.",
  },
  {
    id: "space-atmosphere-motion",
    template_type: "FREE_IMAGE_TO_VIDEO",
    label: "공간 모션",
    category: "GENERAL",
    title: "공간 분위기 모션",
    summary: "공간 사진에 부드러운 카메라 이동과 현실적인 빛 변화를 더합니다.",
    detail: "매장, 방, 작업 공간 같은 사진을 기준으로 구조를 유지하면서 분위기만 살짝 움직입니다.",
    duration_seconds: 5,
    offer_text:
      "장면: 업로드한 공간 사진의 구조와 소품 그대로\n동작: 빛이 천천히 변하며 공간의 분위기만 은은하게 움직임\n카메라: 부드럽게 천천히 이동하는 시네마틱 무빙\n스타일: realistic, cinematic\n금지사항: 텍스트 넣지 말 것, 공간 구조와 소품 배치 유지",
    cta_text: "공간 분위기",
    target_audience: "공간 분위기 영상",
    tone: "CALM",
    disclaimer: "공간 구조와 소품 배치는 원본 그대로 유지합니다.",
  },
];

const serverRoute = [
  "External user",
  "Hairso FE",
  "apimgr",
  "Local AI",
] as const;

const STUDIO_PROJECT_STORAGE_KEY = "hairso.studio.currentProjectId";

type Phase = "idle" | "drafting" | "editing" | "rendering" | "done" | "error";
type FlowStep = (typeof flowSteps)[number]["id"];

function resolveFlowStep(phase: Phase, project: StudioProjectResponse | null): FlowStep {
  if (phase === "done" || (phase === "error" && project?.render_generation_id)) return "result";
  if (phase === "rendering" || project?.render_generation_id) return "render";
  if (phase === "drafting" || project?.draft) return "draft";
  return "templates";
}

function getTemplateOption(templateType: StudioTemplateType): StudioTemplateOption {
  return templateOptions.find((option) => option.template_type === templateType) ?? defaultTemplateOption;
}

function getTemplateOptionById(optionId: string): StudioTemplateOption {
  return templateOptions.find((option) => option.id === optionId) ?? defaultTemplateOption;
}

function getBriefCopy(templateType: StudioTemplateType) {
  if (templateType === "HAIR_STYLING_MOTION") {
    return {
      title: "헤어 연출 입력",
      body: "업로드 사진의 헤어 스타일, 움직임, 유지할 얼굴·모발 조건을 기준으로 만듭니다.",
      titleLabel: "연출 제목",
      actionLabel: "짧은 자막",
      promptLabel: "헤어 스타일링·움직임",
      promptPlaceholder:
        "장면: 어디서, 무엇이 보이는지\n동작: 머릿결이 어떻게 움직이는지\n카메라: 고정, 줌인, 패닝 등\n스타일: realistic, cinematic 같은 영어 키워드 가능\n금지사항: 텍스트 넣지 말 것, 얼굴 왜곡 없게",
      targetLabel: "연출 분위기",
      disclaimerLabel: "유지할 점",
      imageDescription: "얼굴과 헤어가 보이는 사진을 업로드하세요. 첫 번째 이미지가 렌더 기준입니다.",
    };
  }
  if (templateType === "FREE_IMAGE_TO_VIDEO") {
    return {
      title: "장면 입력",
      body: "사진과 프롬프트로 5~30초 영상을 만듭니다. 한글/영어 모두 입력할 수 있습니다.",
      titleLabel: "영상 제목",
      actionLabel: "짧은 자막",
      promptLabel: "자유 프롬프트",
      promptPlaceholder:
        "장면: 어디서, 무엇이 보이는지\n동작: 누가/무엇이 어떻게 움직이는지\n카메라: 고정, 줌인, 패닝, 드론샷 등\n스타일: realistic, cinematic, documentary 같은 영어 키워드 가능\n금지사항: 텍스트 넣지 말 것, 얼굴 왜곡 없게",
      targetLabel: "용도",
      disclaimerLabel: "제약·주의",
      imageDescription: "인물, 공간, 제품, 음식, 풍경 등 원하는 이미지를 업로드할 수 있습니다. 첫 번째 이미지가 기준입니다.",
    };
  }
  return {
    title: "쇼츠 입력",
    body: "게시 전 검토할 제목, 장면 설명, CTA와 안전한 asset_id 참조만 보냅니다.",
    titleLabel: "제목",
    actionLabel: "CTA",
    promptLabel: "장면 설명·안내",
    promptPlaceholder: "장면에서 보여줄 핵심 내용을 입력하세요.",
    targetLabel: "대상",
    disclaimerLabel: "안내 문구",
    imageDescription: "업로드하면 asset_id가 자동으로 반영됩니다. 최대 6개까지 사용할 수 있어요.",
  };
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

function assetIdsToText(assetIds: string[]): string {
  return assetIds.join(", ");
}

function readStoredProjectId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(STUDIO_PROJECT_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStoredProjectId(projectId: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (projectId) {
      window.localStorage.setItem(STUDIO_PROJECT_STORAGE_KEY, projectId);
    } else {
      window.localStorage.removeItem(STUDIO_PROJECT_STORAGE_KEY);
    }
  } catch {
    return;
  }
}

function createRenderIdempotencyKey(): string {
  const randomUUID = globalThis.crypto?.randomUUID;
  if (typeof randomUUID === "function") return randomUUID.call(globalThis.crypto);
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).slice(2, 12);
  return `studio-render-${timestamp}-${random}`;
}

function appendAssetIds(current: string, nextAssetIds: string[]): string {
  const merged: string[] = [];
  for (const assetId of [...parseAssetIds(current), ...nextAssetIds]) {
    if (!merged.includes(assetId)) merged.push(assetId);
    if (merged.length === 6) break;
  }
  return assetIdsToText(merged);
}

function hasInvalidAssetReference(assetIds: string[]): boolean {
  return assetIds.some((assetId) => !STUDIO_ASSET_ID_PATTERN.test(assetId));
}

function hasRenderAssetInput(assetIds: string[]): boolean {
  return assetIds.length > 0;
}

const imageValidationMessages: Record<Exclude<ValidationCode, "OK">, string> = {
  MIME_NOT_ALLOWED: "PNG, JPG, WEBP 이미지만 업로드할 수 있어요.",
  TOO_LARGE: "이미지는 10MB 이하만 업로드할 수 있어요.",
  TOO_SMALL: "이미지는 가로와 세로가 각각 512px 이상이어야 해요.",
};

function messageForImageValidation(code: ValidationCode): string | null {
  if (code === "OK") return null;
  return imageValidationMessages[code];
}

async function readImageDimensions(file: File): Promise<{ width: number; height: number }> {
  if ("createImageBitmap" in globalThis) {
    const bitmap = await createImageBitmap(file);
    try {
      return { width: bitmap.width, height: bitmap.height };
    } finally {
      bitmap.close();
    }
  }

  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    const cleanup = () => URL.revokeObjectURL(url);

    image.onload = () => {
      cleanup();
      resolve({ width: image.naturalWidth, height: image.naturalHeight });
    };
    image.onerror = () => {
      cleanup();
      reject(new Error("image decode failed"));
    };
    image.src = url;
  });
}

async function validateStudioImageFile(file: File): Promise<string | null> {
  const mimeMessage = messageForImageValidation(checkMimeType(file.type).code);
  if (mimeMessage) return mimeMessage;

  const sizeMessage = messageForImageValidation(checkFileSize(file.size).code);
  if (sizeMessage) return sizeMessage;

  try {
    const dimensions = await readImageDimensions(file);
    const result = validateImageMeta({
      mime: file.type,
      bytes: file.size,
      width: dimensions.width,
      height: dimensions.height,
    });
    return messageForImageValidation(result.code);
  } catch {
    return "이미지 파일을 읽을 수 없습니다.";
  }
}

function formatBytes(byteSize: number): string {
  if (byteSize >= 1024 * 1024) return `${(byteSize / (1024 * 1024)).toFixed(1)}MB`;
  if (byteSize >= 1024) return `${Math.round(byteSize / 1024)}KB`;
  return `${byteSize}B`;
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

interface UploadedStudioAsset {
  assetId: string;
  filename: string;
  mimeType: string;
  byteSize: number;
  previewUrl: string;
}

interface UploadedAssetListProps {
  assets: UploadedStudioAsset[];
  disabled: boolean;
  onRemove: (assetId: string) => void;
}

function UploadedAssetList({ assets, disabled, onRemove }: UploadedAssetListProps) {
  if (assets.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-[var(--ui-border-default)] px-3 py-4 text-sm text-[var(--ui-content-muted)]">
        업로드된 이미지가 없습니다.
      </p>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {assets.map((asset) => (
        <div
          key={asset.assetId}
          className="grid grid-cols-[72px_minmax(0,1fr)] gap-3 rounded-lg border border-[var(--ui-border-default)] bg-[var(--ui-surface-elevated)] p-2"
        >
          <div
            aria-hidden="true"
            className="h-[72px] w-[72px] rounded-lg bg-cover bg-center"
            style={{ backgroundImage: `url("${asset.previewUrl}")` }}
          />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-[var(--ui-content-primary)]">{asset.filename}</p>
            <p className="mt-1 text-xs text-[var(--ui-content-muted)]">
              {asset.mimeType} · {formatBytes(asset.byteSize)}
            </p>
            <p className="mt-1 break-all font-mono text-[11px] text-[var(--ui-content-muted)]">
              {asset.assetId}
            </p>
            <button
              type="button"
              onClick={() => onRemove(asset.assetId)}
              disabled={disabled}
              className="mt-2 min-h-8 rounded border border-[var(--ui-border-default)] px-2 text-xs font-semibold text-[var(--ui-content-secondary)] disabled:opacity-50"
            >
              목록에서 제거
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

export function StudioWorkspace() {
  const [selectedTemplateOptionId, setSelectedTemplateOptionId] = useState(defaultTemplateOption.id);
  const [selectedTemplate, setSelectedTemplate] = useState<StudioTemplateType>(
    defaultTemplateOption.template_type,
  );
  const [title, setTitle] = useState(defaultTemplateOption.title);
  const [offerText, setOfferText] = useState(defaultTemplateOption.offer_text);
  const [ctaText, setCtaText] = useState(defaultTemplateOption.cta_text);
  const [durationSeconds, setDurationSeconds] = useState<StudioDurationSeconds>(
    defaultTemplateOption.duration_seconds,
  );
  const [targetAudience, setTargetAudience] = useState(defaultTemplateOption.target_audience);
  const [category, setCategory] = useState<StudioCategory>(defaultTemplateOption.category);
  const [tone, setTone] = useState<StudioTone>(defaultTemplateOption.tone);
  const [assetIdsText, setAssetIdsText] = useState("");
  const [disclaimer, setDisclaimer] = useState(defaultTemplateOption.disclaimer);
  const [uploadedAssets, setUploadedAssets] = useState<UploadedStudioAsset[]>([]);
  const [uploadingAssets, setUploadingAssets] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [project, setProject] = useState<StudioProjectResponse | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [generationStatus, setGenerationStatus] = useState<GenerationStatus | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mounted = useRef(true);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abort = useRef<AbortController | null>(null);
  const renderKey = useRef<string | null>(null);
  const resultSection = useRef<HTMLDivElement | null>(null);
  const previewUrls = useRef<Set<string>>(new Set());
  const restoredProject = useRef(false);

  const cleanup = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    abort.current?.abort();
  }, []);

  const createPreviewUrl = useCallback((file: File) => {
    const url = URL.createObjectURL(file);
    previewUrls.current.add(url);
    return url;
  }, []);

  const revokePreviewUrl = useCallback((url: string) => {
    URL.revokeObjectURL(url);
    previewUrls.current.delete(url);
  }, []);

  const revokeAllPreviewUrls = useCallback(() => {
    for (const url of previewUrls.current) URL.revokeObjectURL(url);
    previewUrls.current.clear();
  }, []);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      cleanup();
      revokeAllPreviewUrls();
    };
  }, [cleanup, revokeAllPreviewUrls]);

  useEffect(() => {
    if (project?.render_generation_id) {
      resultSection.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [project?.render_generation_id]);

  const setApiError = useCallback((err: unknown) => {
    if (isAbortError(err)) return;
    const code = err instanceof ApiError ? err.code : "UNKNOWN";
    setErrorMsg(messageForErrorCode(code));
    setPhase("error");
  }, []);

  const resetRenderState = useCallback(() => {
    writeStoredProjectId(null);
    setProject(null);
    setGenerationStatus(null);
    setErrorMsg(null);
    setPhase("idle");
    renderKey.current = null;
  }, []);

  const handleSelectTemplate = useCallback(
    (optionId: string) => {
      if (phase === "drafting" || phase === "rendering") return;
      cleanup();
      setUploadError(null);
      const option = getTemplateOptionById(optionId);
      setSelectedTemplateOptionId(option.id);
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
    const option = getTemplateOptionById(selectedTemplateOptionId);
    cleanup();
    setSelectedTemplate(option.template_type);
    setCategory(option.category);
    setTitle(option.title);
    setOfferText(option.offer_text);
    setCtaText(option.cta_text);
    setDurationSeconds(option.duration_seconds);
    setTargetAudience(option.target_audience);
    setTone(option.tone);
    setDisclaimer(option.disclaimer);
    setAssetIdsText("");
    setUploadedAssets([]);
    setUploadError(null);
    revokeAllPreviewUrls();
    resetRenderState();
  }, [cleanup, resetRenderState, revokeAllPreviewUrls, selectedTemplateOptionId]);

  const handleAssetUpload = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(event.currentTarget.files ?? []);
      event.currentTarget.value = "";
      if (files.length === 0 || phase === "drafting" || phase === "rendering" || project) return;

      const remainingSlots = Math.max(0, 6 - parseAssetIds(assetIdsText).length);
      if (remainingSlots === 0) {
        setUploadError("이미지는 최대 6개까지 업로드할 수 있어요.");
        return;
      }

      const selectedFiles = files.slice(0, remainingSlots);
      const skippedCount = files.length - selectedFiles.length;
      const uploaded: UploadedStudioAsset[] = [];
      let failed = false;
      setUploadingAssets(true);
      setUploadError(skippedCount > 0 ? "이미지는 최대 6개까지만 반영했어요." : null);

      for (const file of selectedFiles) {
        try {
          const validationError = await validateStudioImageFile(file);
          if (validationError) {
            failed = true;
            setUploadError(validationError);
            break;
          }
          const asset = await uploadAsset(file);
          uploaded.push({
            assetId: asset.asset_id,
            filename: file.name || asset.asset_id,
            mimeType: asset.mime_type,
            byteSize: asset.byte_size,
            previewUrl: createPreviewUrl(file),
          });
        } catch (err) {
          failed = true;
          if (err instanceof ApiError) {
            setUploadError(messageForErrorCode(err.code));
          } else {
            setUploadError("이미지 업로드에 실패했습니다.");
          }
          break;
        }
      }

      if (!mounted.current) {
        uploaded.forEach((asset) => revokePreviewUrl(asset.previewUrl));
        return;
      }

      if (uploaded.length > 0) {
        setUploadedAssets((prev) => [...prev, ...uploaded].slice(0, 6));
        setAssetIdsText((prev) => appendAssetIds(prev, uploaded.map((asset) => asset.assetId)));
      }
      if (!failed && skippedCount === 0) setUploadError(null);
      setUploadingAssets(false);
    },
    [assetIdsText, createPreviewUrl, phase, project, revokePreviewUrl],
  );

  const handleRemoveUploadedAsset = useCallback(
    (assetId: string) => {
      setUploadedAssets((prev) => {
        const target = prev.find((asset) => asset.assetId === assetId);
        if (target) revokePreviewUrl(target.previewUrl);
        return prev.filter((asset) => asset.assetId !== assetId);
      });
      setAssetIdsText((prev) => assetIdsToText(parseAssetIds(prev).filter((item) => item !== assetId)));
    },
    [revokePreviewUrl],
  );

  const refreshProject = useCallback(async (projectId: string) => {
    const refreshed = await getStudioProject(projectId);
    if (!mounted.current) return null;
    setProject(refreshed);
    writeStoredProjectId(refreshed.project_id);
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
          if (res.generation_type !== "VIDEO") {
            setErrorMsg("렌더 상태 응답이 영상 작업과 일치하지 않습니다.");
            setPhase("error");
            return;
          }
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

  const applyProjectToInputs = useCallback((nextProject: StudioProjectResponse) => {
    const option = getTemplateOption(nextProject.template_type);
    setSelectedTemplateOptionId(option.id);
    setSelectedTemplate(nextProject.template_type);
    setCategory(nextProject.category);
    setTitle(nextProject.title);
    setOfferText(nextProject.offer_text);
    setCtaText(nextProject.cta_text);
    setDurationSeconds(nextProject.duration_seconds);
    setTargetAudience(nextProject.target_audience ?? "");
    setTone(nextProject.tone);
    setAssetIdsText(assetIdsToText(nextProject.asset_ids));
    setDisclaimer(nextProject.disclaimer ?? "");
  }, []);

  useEffect(() => {
    if (restoredProject.current) return;
    restoredProject.current = true;

    const storedProjectId = readStoredProjectId();
    if (!storedProjectId) return;

    const controller = new AbortController();
    abort.current = controller;
    const restore = async () => {
      try {
        const restored = await getStudioProject(storedProjectId, controller.signal);
        if (!mounted.current) return;

        setProject(restored);
        applyProjectToInputs(restored);
        writeStoredProjectId(restored.project_id);

        const status = restored.render_status ?? null;
        setGenerationStatus(status);
        if (restored.render_generation_id && status !== null && !TERMINAL.has(status)) {
          setPhase("rendering");
          pollGeneration(restored.project_id, restored.render_generation_id);
          return;
        }
        if (status === "SUCCEEDED") {
          setPhase("done");
          setErrorMsg(null);
          return;
        }
        if (status !== null && TERMINAL.has(status)) {
          setPhase("error");
          setErrorMsg("렌더가 완료되지 못했어요.");
          return;
        }
        setPhase(restored.draft ? "editing" : "idle");
      } catch (err) {
        if (!mounted.current || isAbortError(err)) return;
        if (err instanceof ApiError && err.code === "NOT_FOUND") {
          writeStoredProjectId(null);
          return;
        }
        setApiError(err);
      }
    };

    void restore();
  }, [applyProjectToInputs, pollGeneration, setApiError]);

  const handleCreateDraft = useCallback(async () => {
    cleanup();
    setErrorMsg(null);
    setGenerationStatus(null);
    setPhase("drafting");
    renderKey.current = null;
    try {
      const assetIds = parseAssetIds(assetIdsText);
      if (hasInvalidAssetReference(assetIds)) {
        setErrorMsg("asset_id는 등록된 ID만 입력할 수 있어요.");
        setPhase("idle");
        return;
      }
      if (!hasRenderAssetInput(assetIds)) {
        setErrorMsg("Render하려면 장면 이미지를 먼저 업로드해 주세요.");
        setPhase("idle");
        return;
      }
      const projectTitle =
        title.trim() || (selectedTemplateOptionId === FREE_PROMPT_OPTION_ID ? FREE_PROMPT_PROJECT_TITLE : "");
      const projectCtaText =
        ctaText.trim() || (selectedTemplateOptionId === FREE_PROMPT_OPTION_ID ? FREE_PROMPT_PROJECT_CTA : "");
      if (!projectTitle || !offerText.trim() || !projectCtaText) {
        setErrorMsg("프롬프트를 입력해 주세요.");
        setPhase("idle");
        return;
      }
      const created = await createStudioProject({
        template_type: selectedTemplate,
        category,
        title: projectTitle,
        offer_text: offerText.trim(),
        cta_text: projectCtaText,
        duration_seconds: durationSeconds,
        target_audience: toNullable(targetAudience),
        tone,
        asset_ids: assetIds,
        logo_asset_id: null,
        disclaimer: toNullable(disclaimer),
      });
      const drafted = await createStudioDraft(created.project_id);
      if (!mounted.current) return;
      writeStoredProjectId(drafted.project_id);
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
    offerText,
    selectedTemplateOptionId,
    selectedTemplate,
    setApiError,
    targetAudience,
    title,
    tone,
  ]);

  const handleRender = useCallback(async () => {
    if (!project?.draft) return;
    if (!hasRenderAssetInput(project.asset_ids)) {
      setErrorMsg("이미지가 없는 작업은 렌더할 수 없습니다. 새 작업에서 장면 이미지를 업로드해 주세요.");
      setPhase("editing");
      return;
    }
    cleanup();
    setErrorMsg(null);
    setPhase("rendering");
    try {
      const saved = await updateStudioDraft(project.project_id, {
        script: project.draft.script,
        storyboard: project.draft.storyboard,
      });
      if (!mounted.current) return;
      writeStoredProjectId(saved.project_id);
      setProject(saved);
      const key = renderKey.current ?? createRenderIdempotencyKey();
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
  const assetReferenceError = hasInvalidAssetReference(currentAssetIds);
  const hasSelectedRenderAsset = hasRenderAssetInput(currentAssetIds);
  const uploadBusy = uploadingAssets;
  const freeCustomSelected = selectedTemplateOptionId === FREE_PROMPT_OPTION_ID;
  const projectTitleForSubmit = title.trim() || (freeCustomSelected ? FREE_PROMPT_PROJECT_TITLE : "");
  const projectCtaTextForSubmit = ctaText.trim() || (freeCustomSelected ? FREE_PROMPT_PROJECT_CTA : "");
  const canDraft = Boolean(
    projectTitleForSubmit &&
      offerText.trim() &&
      projectCtaTextForSubmit &&
      hasSelectedRenderAsset &&
      !assetReferenceError &&
      !uploadBusy,
  );
  const busy = phase === "drafting" || phase === "rendering" || uploadBusy;
  const activeStep = resolveFlowStep(phase, project);
  const activeStepIndex = flowSteps.findIndex((step) => step.id === activeStep);
  const activeStepLabel = flowSteps.find((step) => step.id === activeStep)?.label ?? "템플릿";
  const renderStatus = generationStatus ?? project?.render_status ?? null;
  const selectedTemplateOption = getTemplateOptionById(selectedTemplateOptionId);
  const briefCopy = getBriefCopy(selectedTemplate);
  const previewDurationSeconds = durationSeconds;
  const projectHasRenderAsset = project ? hasRenderAssetInput(project.asset_ids) : false;
  const hasResult = phase === "done" || (phase === "error" && Boolean(project?.render_generation_id));
  const outputReady = Boolean(project?.project_id && project.output_asset_id && renderStatus === "SUCCEEDED");
  const downloadPath = outputReady && project ? getStudioProjectDownloadPath(project.project_id) : null;
  const canRender = Boolean(project?.draft && projectHasRenderAsset && !busy && !project.render_generation_id);
  const draftLocked = busy || Boolean(project?.render_generation_id);
  const inputLocked = busy || Boolean(project);
  const outputSummary = `${project?.duration_seconds ?? durationSeconds}s · 9:16 · 480p`;
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
                    Studio · Local-first
                  </p>
                  <h1 className="sr-only">Hairso Studio</h1>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--ui-content-secondary)]">
                    업로드 이미지와 프롬프트로 자유 영상을 만들고, 필요할 때 헤어·제품·공간 프리셋으로 빠르게 시작합니다.
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
            eyebrow="템플릿"
            title="제작 유형"
            body="원하는 연출을 먼저 고르고, 자세한 설명은 펼쳐서 확인하세요."
            action={<span className="studio-pill px-3 py-1 text-xs font-semibold">{activeStepLabel}</span>}
          >
            <fieldset className="mt-4">
              <legend className="sr-only">Studio template</legend>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
                {templateOptions.map((option) => {
                  const selected = selectedTemplateOptionId === option.id;
                  const durationLabel = `${option.duration_seconds}초`;
                  return (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => handleSelectTemplate(option.id)}
                      disabled={busy}
                      aria-pressed={selected}
                      className={`h-20 overflow-hidden rounded-lg border p-2 text-left transition-colors disabled:opacity-60 ${
                        selected
                          ? "border-[var(--ui-action-primary)] bg-[var(--ui-action-primary)] text-[var(--ui-action-on-primary)]"
                          : "border-[var(--ui-border-default)] bg-[var(--ui-surface-elevated)] text-[var(--ui-content-primary)] hover:border-[var(--ui-border-strong)]"
                      }`}
                    >
                      <span
                        className={`block truncate text-[10px] font-semibold uppercase leading-none ${
                          selected ? "text-[var(--ui-content-inverse-muted)]" : "text-[var(--ui-action-accent)]"
                        }`}
                      >
                        {templateLabels[option.template_type]}
                      </span>
                      <span className="mt-2 block truncate text-sm font-bold leading-tight">{option.label}</span>
                      <span
                        className={`mt-2 block truncate text-[11px] leading-tight ${
                          selected ? "text-[var(--ui-content-inverse-muted)]" : "text-[var(--ui-content-muted)]"
                        }`}
                      >
                        {categoryLabels[option.category]} · {durationLabel} · {toneLabels[option.tone]}
                      </span>
                    </button>
                  );
                })}
              </div>
            </fieldset>
            <details className="mt-3 rounded-lg border border-[var(--ui-border-default)] bg-[var(--ui-surface-elevated)]">
              <summary className="cursor-pointer px-3 py-2 text-sm font-semibold text-[var(--ui-content-primary)]">
                선택 템플릿 자세히 보기
              </summary>
              <div className="border-t border-[var(--ui-border-default)] px-3 py-3 text-sm leading-6 text-[var(--ui-content-secondary)]">
                {selectedTemplateOption.title && (
                  <p className="font-semibold text-[var(--ui-content-primary)]">{selectedTemplateOption.title}</p>
                )}
                <p className="mt-1">{selectedTemplateOption.summary}</p>
                <p className="mt-1">{selectedTemplateOption.detail}</p>
              </div>
            </details>
          </StudioSection>

          <StudioSection
            eyebrow="Brief"
            title={briefCopy.title}
            body={briefCopy.body}
            action={
              project ? (
                <span className="studio-pill break-all px-3 py-1 font-mono text-xs">{project.project_id}</span>
              ) : null
            }
          >
            <fieldset className="mt-4">
              <legend className="studio-label">카테고리</legend>
              <div className="mt-2 grid grid-cols-2 overflow-hidden rounded-lg border border-[var(--ui-border-default)] sm:grid-cols-4 lg:grid-cols-7">
                {studioCategories.map((item) => (
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

            {!freeCustomSelected && (
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <Field label={briefCopy.titleLabel}>
                  <input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    disabled={inputLocked}
                    className="studio-input px-3 text-base disabled:opacity-60"
                  />
                </Field>
                <Field label={briefCopy.actionLabel}>
                  <input
                    value={ctaText}
                    onChange={(e) => setCtaText(e.target.value)}
                    disabled={inputLocked}
                    className="studio-input px-3 text-base disabled:opacity-60"
                  />
                </Field>
              </div>
            )}

            <div className="mt-4">
              <Field label={briefCopy.promptLabel}>
                <textarea
                  value={offerText}
                  onChange={(e) => setOfferText(e.target.value)}
                  placeholder={briefCopy.promptPlaceholder}
                  rows={6}
                  disabled={inputLocked}
                  className="studio-input min-h-[168px] resize-none p-3 text-base placeholder:text-[var(--ui-content-muted)] disabled:opacity-60"
                />
              </Field>
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Field label={briefCopy.targetLabel}>
                <input
                  value={targetAudience}
                  onChange={(e) => setTargetAudience(e.target.value)}
                  disabled={inputLocked}
                  className="studio-input px-3 text-base disabled:opacity-60"
                />
              </Field>
              <Field label={briefCopy.disclaimerLabel}>
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
                <div className="mt-2 grid grid-cols-3 overflow-hidden rounded-lg border border-[var(--ui-border-default)]">
                  {durationOptions.map((seconds) => (
                    <button
                      key={seconds}
                      type="button"
                      onClick={() => setDurationSeconds(seconds)}
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

            <div className="mt-4 grid gap-4">
              <div className="studio-muted-tile p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="studio-label">장면 이미지</p>
                    <p className="mt-1 text-sm leading-6 text-[var(--ui-content-secondary)]">
                      {briefCopy.imageDescription}
                    </p>
                  </div>
                  <label
                    className={`inline-flex min-h-11 cursor-pointer items-center justify-center rounded-lg border border-[var(--ui-border-default)] bg-[var(--ui-surface-elevated)] px-4 text-sm font-semibold text-[var(--ui-content-primary)] transition-colors hover:bg-[var(--ui-surface-muted)] ${
                      inputLocked ? "pointer-events-none opacity-50" : ""
                    }`}
                  >
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      multiple
                      onChange={handleAssetUpload}
                      disabled={inputLocked}
                      className="sr-only"
                    />
                    {uploadingAssets ? "업로드 중..." : "이미지 업로드"}
                  </label>
                </div>
                <div className="mt-3">
                  <UploadedAssetList
                    assets={uploadedAssets}
                    disabled={inputLocked}
                    onRemove={handleRemoveUploadedAsset}
                  />
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="이미지 asset_id" hint="업로드 후 자동 입력됩니다. 직접 붙여넣기도 가능합니다.">
                  <input
                    value={assetIdsText}
                    onChange={(e) => setAssetIdsText(e.target.value)}
                    disabled={inputLocked}
                    placeholder="asset-1, asset-2"
                    className="studio-input px-3 text-base disabled:opacity-60"
                  />
                </Field>
              </div>
            </div>
            {uploadError && (
              <p
                className="mt-3 rounded-lg bg-[var(--ui-status-error-bg)] px-3 py-2 text-sm text-[var(--ui-status-error-text)]"
                role="alert"
              >
                {uploadError}
              </p>
            )}
            {assetReferenceError && (
              <p
                className="mt-3 rounded-lg bg-[var(--ui-status-error-bg)] px-3 py-2 text-sm text-[var(--ui-status-error-text)]"
                role="alert"
              >
                asset_id는 등록된 ID만 입력할 수 있어요.
              </p>
            )}
            {!hasSelectedRenderAsset && !project && (
              <p className="mt-3 rounded-lg bg-[var(--ui-surface-muted)] px-3 py-2 text-sm text-[var(--ui-content-secondary)]" role="status">
                Render하려면 장면 이미지나 로고를 먼저 업로드해 주세요.
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
                <DetailRow label="Output" value={outputSummary} />
                <DetailRow label="템플릿" value={templateLabels[project.template_type]} />
                <DetailRow label="Scenes" value={`${project.draft.storyboard.length}개 · ${storyboardDuration ?? 0}s`} />
                <DetailRow
                  label="Storage"
                  value={`${project.storage.backend} · ${project.storage.output_retention_days}d`}
                />
              </div>
              {!projectHasRenderAsset && (
                <p
                  className="mt-3 rounded-lg bg-[var(--ui-status-error-bg)] px-3 py-2 text-sm text-[var(--ui-status-error-text)]"
                  role="alert"
                >
                  이미지가 없는 작업은 렌더할 수 없습니다. 새 작업에서 장면 이미지를 업로드해 주세요.
                </p>
              )}
              <Button
                className="mt-5 w-full sm:w-auto"
                onClick={handleRender}
                disabled={!canRender}
                aria-busy={phase === "rendering"}
              >
                {phase === "rendering" ? "렌더 진행 중..." : "Render 시작"}
              </Button>
              {phase === "rendering" && !project.render_generation_id && (
                <p className="mt-3 rounded-lg bg-[var(--ui-surface-muted)] px-3 py-2 text-sm text-[var(--ui-content-secondary)]" role="status">
                  렌더 요청을 서버에 등록 중입니다. 다시 누르지 않아도 됩니다.
                </p>
              )}
              {phase === "rendering" && project.render_generation_id && (
                <p className="mt-3 rounded-lg bg-[var(--ui-surface-muted)] px-3 py-2 text-sm text-[var(--ui-content-secondary)]" role="status">
                  이 PC의 AI 서버에서 영상을 만드는 중입니다. 5초 영상은 보통 8~10분 걸리며, 완료되면 Download가 켜집니다.
                </p>
              )}
            </StudioSection>
          )}

          <div ref={resultSection}>
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
                    결과 파일이 준비되었습니다. 핸드폰에서는 Download를 누르면 기본 다운로드 경로에 저장됩니다.
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
                  <button
                    type="button"
                    disabled
                    className="min-h-11 rounded-lg border border-[var(--ui-border-default)] bg-[var(--ui-surface-muted)] text-xs font-semibold text-[var(--ui-content-muted)]"
                  >
                    Preview
                  </button>
                  {downloadPath ? (
                    <a
                      href={downloadPath}
                      download
                      className="inline-flex min-h-11 items-center justify-center rounded-lg bg-[var(--ui-action-primary)] px-3 text-xs font-semibold text-[var(--ui-action-on-primary)] transition-colors hover:bg-[var(--ui-action-primary-hover)]"
                    >
                      Download
                    </a>
                  ) : (
                    <button
                      type="button"
                      disabled
                      className="min-h-11 rounded-lg border border-[var(--ui-border-default)] bg-[var(--ui-surface-muted)] text-xs font-semibold text-[var(--ui-content-muted)]"
                    >
                      Download
                    </button>
                  )}
                  <button
                    type="button"
                    disabled
                    className="min-h-11 rounded-lg border border-[var(--ui-border-default)] bg-[var(--ui-surface-muted)] text-xs font-semibold text-[var(--ui-content-muted)]"
                  >
                    QR
                  </button>
                </div>
              </StudioSection>
            )}
          </div>
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
                  <span>{previewDurationSeconds}s</span>
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
                      <span className="rounded bg-[var(--ui-border-inverse)] px-2 py-1">02 · Motion</span>
                      <span className="rounded bg-[var(--ui-border-inverse)] px-2 py-1">03 · Cue</span>
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
                <span className="text-[var(--ui-content-inverse-muted)]">템플릿</span>
                <span className="font-semibold">{selectedTemplateOption.label}</span>
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

            {errorMsg && !hasResult && (
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
