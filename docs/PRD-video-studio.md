# PRD - Hairso Studio Video MVP

## Summary

Hairso Studio turns salon photos and short prompts into vertical videos. The first product goal is not a general-purpose AI video editor. It is one dependable salon workflow that creates a 9:16 promotional or consultation short from existing Hairso capabilities.

The MVP must preserve the current mock scaffold and complete one reliable flow before adding paid providers, a professional editor, or automatic social publishing.

## Product Principles

- Start with salon use cases, not a generic video generator.
- Prefer composed videos: script, storyboard, images or clips, TTS, captions, transitions, and FFmpeg-style final rendering.
- Use generated-video providers only for bounded scene assets, not for one opaque long final video.
- Keep provider credentials and provider calls backend-only.
- Keep customer images, signed URLs, Base64 payloads, and provider raw payloads out of FE storage, logs, and external review payloads.

## Target User

- Salon owner
- Hair designer
- Beauty shop marketer
- Later: creators making hair, beauty, health, and product information shorts

## MVP Workflow

1. User opens the dashboard and selects a video template.
2. User uploads up to 6 images and optionally 1 logo.
3. User enters a promotion, topic, price, offer, or explanation.
4. System drafts a title, hook, narration, captions, scenes, and call to action.
5. User edits the script and storyboard.
6. User starts generation.
7. Backend creates or requests assets, voice, captions, and render work.
8. System renders a 9:16 MP4.
9. User previews, downloads, regenerates, or shares the result by QR.

## Current Baseline

The repository already has a lower-level mock generation scaffold:

- FE can call `POST /api/v1/video-generations` and poll `GET /api/v1/generations/{id}` from `hairsoui/src/features/video-generation/GenerationFlow.tsx`.
- BE owns provider submission, status mapping, idempotency, and cost fields through the generation service and provider abstractions.
- The current status contract has 10 values: `CREATED`, `UPLOADING`, `SUBMITTED`, `QUEUED`, `PROCESSING`, `POST_PROCESSING`, `SUCCEEDED`, `FAILED`, `CANCELED`, `EXPIRED`.
- Mock providers are the default local path. Real PixVerse, Wan, fal, Gemini, FFmpeg/R2 post-processing, credits, auth, QR/share, and real uploads remain roadmap unless separately implemented.

This PRD describes the Studio product layer to build on top of that scaffold. It is not permission to rename working FE/BE modules or replace the current generation API in one step.

## Initial Templates

### Before/After

For treatment result videos using uploaded before/after images.

### Event Promotion

For short promotional reels with price, offer, designer, and booking CTA.

### Information Short

For hair, beauty, product, or health explanations using approved source material.

## Functional Scope

### Inputs

- Template type
- Topic or promotion text
- Optional target audience
- Tone
- Duration: 15s or 30s
- Aspect ratio: 9:16
- Images: up to 6
- Logo: up to 1
- CTA text

The Studio output duration is 15s or 30s. Existing low-level video provider clips may still use shorter provider-specific durations, such as the current 5s or 8s request contract, as bounded scene assets inside the composed final video.

### Generated Content

- Title
- First 3-second hook
- Scene-by-scene narration
- Captions
- Visual prompts
- Optional disclaimer
- TTS voice
- Basic scene transitions
- MP4 output

For information shorts, health or medical-adjacent content must be based on user-provided or explicitly approved source material. The system must not automatically gather medical claims and present them as reviewed facts.

### Result Actions

- Preview
- Download
- QR/share
- Regenerate
- Edit script and rerender

## Out of Scope

- Full timeline editor
- Auto-publishing to social networks
- Multi-avatar video
- Real-time lip sync
- Horizontal and square video output
- Free-form animation controls
- Automatic unsupervised medical research
- Direct provider calls from the frontend
- Automatic use of paid external AI providers during local tests or mock validation
- Customer image caching in browser storage or service workers

## Architecture Direction

Keep the existing FE/BE split.

- FE owns upload, template selection, script/storyboard editing, polling, preview, and sharing.
- BE owns project state, script/storyboard generation, provider adapters, voice generation, rendering, job state, idempotency, and cost records.
- External AI/video providers are backend-only.
- Final videos should be composed by a renderer such as FFmpeg rather than generated as one opaque long video.

### API Surface Direction

The first Studio layer should be thin and compatible with the current scaffold:

- Create or select a Studio project with template, input text, duration, CTA, and uploaded asset IDs.
- Draft script and storyboard in a deterministic mock path first.
- Persist edited script/storyboard before generation.
- Start a render/generation job with an idempotency key.
- Poll job state through the existing generation status contract where possible.
- Return a result reference such as `output_asset_id`, not a signed storage URL.

OpenAPI remains the BE contract source of truth. FE Zod schemas must validate responses at the API boundary.

## Suggested Domain Model

- `ContentProject`
- `Source`
- `Script`
- `Scene`
- `GenerationJob`
- `RenderOutput`

These names are direction, not permission for a large rename. Prefer adding thin compatibility layers over renaming existing working modules all at once.

## Status Model Direction

Keep the existing 10-state generation contract as the integration baseline:

```text
CREATED
UPLOADING
SUBMITTED
QUEUED
PROCESSING
POST_PROCESSING
SUCCEEDED
FAILED
CANCELED
EXPIRED
```

Studio-specific phases such as scripting, asset generation, voice generation, and rendering can be represented as project or scene metadata, or mapped onto the existing generation states, until the product proves that a separate public state contract is necessary.

Preserve idempotency and polling safety. Refreshing or double-clicking should not create duplicate paid jobs.

## First Implementation Milestone

Complete one mock Studio end-to-end flow:

```text
template selected
-> project created
-> image/logo asset IDs accepted or mocked
-> mock script and storyboard drafted
-> user edits script/storyboard
-> mock render job created
-> status polled
-> result page shown with preview/download/share placeholders
```

This milestone proves the workflow before adding real paid providers.

### Acceptance Criteria

- The current `/try` mock generation flow keeps working.
- One template, preferably Event Promotion or Before/After, can run from input to result without paid provider calls.
- Script and storyboard are visible and editable before generation starts.
- Repeated generate clicks or page refreshes do not create duplicate paid jobs; idempotency keys are used intentionally.
- FE never sends provider credentials or calls external AI providers directly.
- BE logs use IDs such as `asset_id`, `generation_id`, and `project_id`, not image URLs, signed URLs, Base64 payloads, or secrets.
- Result state reaches a clear terminal state: success with preview/result reference, or failure with safe user-facing error messaging.
- The implementation can be verified locally with mock providers and without running DB migrations.

## Near-Term Sequence

1. Preserve current Hairso and mock generation flows.
2. Add the smallest Studio project/template layer needed for one flow.
3. Add mock script/storyboard draft and edit persistence.
4. Connect edited storyboard to the existing mock generation job path.
5. Add result preview and download/share placeholders without public signed URLs.
6. Only then add real uploads, FFmpeg/R2 rendering, QR/share tokens, credits, auth hardening, and real provider adapters.

## Open Decisions

- Exact persistence shape for `ContentProject`, `Script`, `Scene`, and `RenderOutput`.
- Whether Studio phases need a separate public status contract or can stay internal metadata.
- Whether the first template should be Event Promotion or Before/After.
- How QR/share should expire and authorize access when implemented.
- How final 15s/30s composed output maps to short provider-generated scene clips.
