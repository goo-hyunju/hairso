"""Studio API 왕복 테스트 — mock-only project/draft/render 흐름."""

import os
import unittest

os.environ.setdefault("MOCK_ADVANCE_INTERVAL_SEC", "0")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


class TestStudioApi(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(main.app)

    def _create_project(
        self,
        template_type: str = "PROMOTION_SHORT",
        category: str = "HAIR",
        duration_seconds: int = 15,
        asset_ids: list[str] | None = None,
        logo_asset_id: str | None = None,
    ) -> str:
        r = self.c.post(
            "/api/v1/studio/projects",
            json={
                "template_type": template_type,
                "category": category,
                "title": "봄맞이 클리닉 이벤트",
                "offer_text": "첫 방문 20% 할인, 이번 달 한정",
                "cta_text": "오늘 예약 문의하기",
                "duration_seconds": duration_seconds,
                "target_audience": "신규 고객",
                "tone": "FRIENDLY",
                "asset_ids": asset_ids or [],
                "logo_asset_id": logo_asset_id,
                "disclaimer": "상세 조건은 매장 상담 후 확정됩니다.",
            },
        )
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertEqual(body["template_type"], template_type)
        self.assertEqual(body["category"], category)
        self.assertEqual(body["status"], "DRAFTING")
        self.assertEqual(body["storage"]["output_prefix"], "studio/outputs")
        self.assertNotIn("storage_key", str(body))
        self.assertNotIn("signed", str(body).lower())
        return body["project_id"]

    def test_studio_project_draft_render_flow(self):
        project_id = self._create_project()

        drafted = self.c.post(f"/api/v1/studio/projects/{project_id}/draft")
        self.assertEqual(drafted.status_code, 200)
        draft_body = drafted.json()
        self.assertEqual(draft_body["status"], "DRAFT_READY")
        self.assertEqual(draft_body["draft"]["version"], 1)
        self.assertEqual(len(draft_body["draft"]["storyboard"]), 3)

        patch_payload = {
            "script": {
                "hook": "이번 주만 가능한 클리닉 혜택을 소개합니다.",
                "narration": [
                    "손상 모발을 위한 집중 케어를 준비했습니다.",
                    "상담 후 모발 상태에 맞춰 단계를 추천합니다.",
                ],
                "cta": "오늘 예약 문의하기",
            },
            "storyboard": [
                {
                    "scene_index": 1,
                    "duration_seconds": 5,
                    "caption": "봄맞이 클리닉 이벤트",
                    "visual_prompt": "clean salon treatment close-up, vertical 9:16",
                }
            ],
        }
        patched = self.c.patch(
            f"/api/v1/studio/projects/{project_id}/draft",
            json=patch_payload,
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["draft"]["version"], 2)

        first_render = self.c.post(
            f"/api/v1/studio/projects/{project_id}/render",
            json={"idempotency_key": "studio-flow-render-1"},
        )
        self.assertEqual(first_render.status_code, 202)
        generation_id = first_render.json()["generation_id"]

        second_render = self.c.post(
            f"/api/v1/studio/projects/{project_id}/render",
            json={"idempotency_key": "studio-flow-render-2"},
        )
        self.assertEqual(second_render.status_code, 202)
        self.assertEqual(second_render.json()["generation_id"], generation_id)

        project = self.c.get(f"/api/v1/studio/projects/{project_id}")
        self.assertEqual(project.status_code, 200)
        project_body = project.json()
        self.assertEqual(project_body["render_generation_id"], generation_id)
        self.assertIn(
            project_body["render_status"],
            ["SUBMITTED", "QUEUED", "PROCESSING", "POST_PROCESSING", "SUCCEEDED"],
        )

    def test_studio_render_requires_draft(self):
        project_id = self._create_project()
        r = self.c.post(
            f"/api/v1/studio/projects/{project_id}/render",
            json={"idempotency_key": "studio-no-draft-render"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["error_code"], "VALIDATION_ERROR")

    def test_salon_event_template_creates_30_second_draft(self):
        project_id = self._create_project(
            template_type="SALON_EVENT_PROMOTION",
            category="LOCAL_BUSINESS",
            duration_seconds=30,
        )
        drafted = self.c.post(f"/api/v1/studio/projects/{project_id}/draft")
        self.assertEqual(drafted.status_code, 200)
        body = drafted.json()
        self.assertEqual(body["template_type"], "SALON_EVENT_PROMOTION")
        self.assertEqual(body["category"], "LOCAL_BUSINESS")
        self.assertEqual(len(body["draft"]["storyboard"]), 5)
        self.assertEqual(
            sum(scene["duration_seconds"] for scene in body["draft"]["storyboard"]),
            30,
        )

    def test_studio_project_rejects_url_asset_id(self):
        r = self.c.post(
            "/api/v1/studio/projects",
            json={
                "template_type": "PROMOTION_SHORT",
                "category": "HAIR",
                "title": "봄맞이 클리닉 이벤트",
                "offer_text": "첫 방문 20% 할인",
                "cta_text": "오늘 예약 문의하기",
                "duration_seconds": 15,
                "target_audience": "신규 고객",
                "tone": "FRIENDLY",
                "asset_ids": ["https://example.com/face.png"],
                "logo_asset_id": None,
                "disclaimer": None,
            },
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["error"]["error_code"], "VALIDATION_ERROR")

    def test_studio_project_rejects_unknown_asset_id(self):
        r = self.c.post(
            "/api/v1/studio/projects",
            json={
                "template_type": "PROMOTION_SHORT",
                "category": "HAIR",
                "title": "봄맞이 클리닉 이벤트",
                "offer_text": "첫 방문 20% 할인",
                "cta_text": "오늘 예약 문의하기",
                "duration_seconds": 15,
                "target_audience": "신규 고객",
                "tone": "FRIENDLY",
                "asset_ids": ["11111111-1111-4111-8111-111111111111"],
                "logo_asset_id": None,
                "disclaimer": None,
            },
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["error_code"], "ASSET_NOT_FOUND")

    def test_studio_project_rejects_sensitive_text_reference(self):
        r = self.c.post(
            "/api/v1/studio/projects",
            json={
                "template_type": "PROMOTION_SHORT",
                "category": "HAIR",
                "title": "봄맞이 클리닉 이벤트",
                "offer_text": "결과 보기 https://example.com/signed-face.png",
                "cta_text": "오늘 예약 문의하기",
                "duration_seconds": 15,
                "target_audience": "신규 고객",
                "tone": "FRIENDLY",
                "asset_ids": [],
                "logo_asset_id": None,
                "disclaimer": None,
            },
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["error_code"], "VALIDATION_ERROR")

    def test_studio_draft_patch_rejects_sensitive_visual_prompt(self):
        project_id = self._create_project()
        drafted = self.c.post(f"/api/v1/studio/projects/{project_id}/draft")
        self.assertEqual(drafted.status_code, 200)

        r = self.c.patch(
            f"/api/v1/studio/projects/{project_id}/draft",
            json={
                "script": {
                    "hook": "이번 주만 가능한 혜택입니다.",
                    "narration": ["안전한 문구입니다."],
                    "cta": "오늘 예약 문의하기",
                },
                "storyboard": [
                    {
                        "scene_index": 1,
                        "duration_seconds": 5,
                        "caption": "안전한 자막",
                        "visual_prompt": "data:image/png;base64,abcdef",
                    }
                ],
            },
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["error_code"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
