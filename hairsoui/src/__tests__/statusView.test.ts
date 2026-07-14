import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// generationStatusView 는 `import type` 만 쓰므로(런타임 erase) alias 없이 로드된다.
import { generationStatusView } from "../features/video-generation/generationStatusView";

const contract = JSON.parse(
  readFileSync(resolve(process.cwd(), "contract/enums.json"), "utf-8"),
) as Record<string, string[]>;

const statuses: string[] = contract.GenerationStatus ?? [];

test("generationStatusView 는 10개 상태 전부에 뷰를 갖는다", () => {
  assert.ok(statuses.length > 0, "contract.GenerationStatus 가 비어 있음");
  for (const status of statuses) {
    assert.ok(status in generationStatusView, `missing view for ${status}`);
  }
  assert.equal(Object.keys(generationStatusView).length, statuses.length);
});

test("종료 상태 isTerminal 플래그", () => {
  assert.equal(generationStatusView.SUCCEEDED.isTerminal, true);
  assert.equal(generationStatusView.FAILED.isTerminal, true);
  assert.equal(generationStatusView.PROCESSING.isTerminal, false);
});
