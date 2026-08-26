"""Studio 저장소의 Supabase(psycopg 동기) 구현.

마이그레이션 실행은 사용자 승인 대상이다. 이 구현은 `db/migrations/0003_studio_mvp.sql`
스키마가 적용된 환경에서만 활성화한다.
"""

from __future__ import annotations

import uuid
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.domain.enums import StudioCategory, StudioProjectStatus, StudioTemplateType, StudioTone
from app.domain.studio import StudioDraft, StudioProject, StudioScene, StudioScript
from app.repositories.studio_repository import StudioRepository

_PROJECT_COLUMNS = (
    "id, template_type, category, status, title, offer_text, cta_text, duration_seconds, "
    "target_audience, tone, disclaimer, created_by, storage_profile_name, "
    "render_generation_id, output_asset_id, created_at, updated_at"
)


def _uid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None


def _script_to_json(script: StudioScript) -> dict[str, Any]:
    return {"hook": script.hook, "narration": list(script.narration), "cta": script.cta}


def _scene_to_json(scene: StudioScene) -> dict[str, Any]:
    return {
        "scene_index": scene.scene_index,
        "duration_seconds": scene.duration_seconds,
        "caption": scene.caption,
        "visual_prompt": scene.visual_prompt,
    }


def _json_to_script(data: dict[str, Any]) -> StudioScript:
    narration = data.get("narration")
    return StudioScript(
        hook=str(data.get("hook", "")),
        narration=[str(item) for item in narration] if isinstance(narration, list) else [],
        cta=str(data.get("cta", "")),
    )


def _json_to_scene(data: dict[str, Any]) -> StudioScene:
    return StudioScene(
        scene_index=int(data.get("scene_index", 1)),
        duration_seconds=int(data.get("duration_seconds", 5)),
        caption=str(data.get("caption", "")),
        visual_prompt=str(data.get("visual_prompt", "")),
    )


def _row_to_project(
    row: dict[str, Any],
    asset_ids: list[str],
    logo_asset_id: str | None,
    draft: StudioDraft | None,
) -> StudioProject:
    return StudioProject(
        id=str(row["id"]),
        template_type=StudioTemplateType(row["template_type"]),
        category=StudioCategory(row["category"]),
        status=StudioProjectStatus(row["status"]),
        title=row["title"],
        offer_text=row["offer_text"],
        cta_text=row["cta_text"],
        duration_seconds=row["duration_seconds"],
        target_audience=row["target_audience"],
        tone=StudioTone(row["tone"]),
        asset_ids=asset_ids,
        logo_asset_id=logo_asset_id,
        disclaimer=row["disclaimer"],
        created_by=str(row["created_by"]) if row["created_by"] is not None else None,
        storage_profile_name=row["storage_profile_name"],
        draft=draft,
        render_generation_id=(
            str(row["render_generation_id"]) if row["render_generation_id"] is not None else None
        ),
        output_asset_id=str(row["output_asset_id"]) if row["output_asset_id"] is not None else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SupabaseStudioRepository(StudioRepository):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def save(self, project: StudioProject) -> StudioProject:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            conn.execute(
                """
                INSERT INTO public.studio_projects
                    (id, template_type, category, status, title, offer_text, cta_text, duration_seconds,
                     target_audience, tone, disclaimer, created_by, storage_profile_name,
                     render_generation_id, output_asset_id, created_at, updated_at)
                VALUES
                    (%(id)s, %(template_type)s, %(category)s, %(status)s, %(title)s, %(offer_text)s,
                     %(cta_text)s, %(duration_seconds)s, %(target_audience)s, %(tone)s,
                     %(disclaimer)s, %(created_by)s, %(storage_profile_name)s,
                     %(render_generation_id)s, %(output_asset_id)s, %(created_at)s, %(updated_at)s)
                """,
                self._project_params(project),
            )
            self._replace_assets(conn, project)
            self._replace_current_draft(conn, project)
        return project

    def update(self, project: StudioProject) -> StudioProject:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            conn.execute(
                """
                UPDATE public.studio_projects SET
                    template_type=%(template_type)s, category=%(category)s, status=%(status)s, title=%(title)s,
                    offer_text=%(offer_text)s, cta_text=%(cta_text)s,
                    duration_seconds=%(duration_seconds)s, target_audience=%(target_audience)s,
                    tone=%(tone)s, disclaimer=%(disclaimer)s, storage_profile_name=%(storage_profile_name)s,
                    render_generation_id=%(render_generation_id)s, output_asset_id=%(output_asset_id)s,
                    updated_at=%(updated_at)s
                WHERE id=%(id)s
                """,
                self._project_params(project),
            )
            self._replace_assets(conn, project)
            self._replace_current_draft(conn, project)
        return project

    def get(self, project_id: str) -> StudioProject | None:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                f"SELECT {_PROJECT_COLUMNS} FROM public.studio_projects WHERE id=%s",
                (_uid(project_id),),
            ).fetchone()
            if row is None:
                return None
            asset_rows = conn.execute(
                """
                SELECT asset_id, asset_role
                FROM public.studio_project_assets
                WHERE project_id=%s
                ORDER BY asset_role, sort_order, created_at
                """,
                (_uid(project_id),),
            ).fetchall()
            draft_row = conn.execute(
                """
                SELECT version, script, storyboard, updated_at
                FROM public.studio_drafts
                WHERE project_id=%s AND is_current=true
                ORDER BY version DESC
                LIMIT 1
                """,
                (_uid(project_id),),
            ).fetchone()

        image_ids: list[str] = []
        logo_asset_id: str | None = None
        for item in asset_rows:
            if item["asset_role"] == "LOGO":
                logo_asset_id = str(item["asset_id"])
            else:
                image_ids.append(str(item["asset_id"]))

        draft = None
        if draft_row is not None:
            storyboard_json = draft_row["storyboard"]
            draft = StudioDraft(
                version=draft_row["version"],
                script=_json_to_script(draft_row["script"]),
                storyboard=[
                    _json_to_scene(scene)
                    for scene in storyboard_json
                    if isinstance(scene, dict)
                ],
                updated_at=draft_row["updated_at"],
            )
        return _row_to_project(row, image_ids, logo_asset_id, draft)

    def _project_params(self, project: StudioProject) -> dict[str, Any]:
        return {
            "id": _uid(project.id),
            "template_type": project.template_type.value,
            "category": project.category.value,
            "status": project.status.value,
            "title": project.title,
            "offer_text": project.offer_text,
            "cta_text": project.cta_text,
            "duration_seconds": project.duration_seconds,
            "target_audience": project.target_audience,
            "tone": project.tone.value,
            "disclaimer": project.disclaimer,
            "created_by": _uid(project.created_by),
            "storage_profile_name": project.storage_profile_name,
            "render_generation_id": _uid(project.render_generation_id),
            "output_asset_id": _uid(project.output_asset_id),
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        }

    def _replace_assets(self, conn, project: StudioProject) -> None:
        project_uuid = _uid(project.id)
        conn.execute("DELETE FROM public.studio_project_assets WHERE project_id=%s", (project_uuid,))
        for index, asset_id in enumerate(project.asset_ids):
            conn.execute(
                """
                INSERT INTO public.studio_project_assets
                    (project_id, asset_id, asset_role, sort_order)
                VALUES (%s, %s, 'IMAGE', %s)
                """,
                (project_uuid, _uid(asset_id), index),
            )
        if project.logo_asset_id:
            conn.execute(
                """
                INSERT INTO public.studio_project_assets
                    (project_id, asset_id, asset_role, sort_order)
                VALUES (%s, %s, 'LOGO', 0)
                """,
                (project_uuid, _uid(project.logo_asset_id)),
            )

    def _replace_current_draft(self, conn, project: StudioProject) -> None:
        if project.draft is None:
            return
        project_uuid = _uid(project.id)
        conn.execute(
            "UPDATE public.studio_drafts SET is_current=false WHERE project_id=%s AND is_current=true",
            (project_uuid,),
        )
        conn.execute(
            """
            INSERT INTO public.studio_drafts
                (project_id, version, script, storyboard, is_current, updated_at)
            VALUES (%s, %s, %s, %s, true, %s)
            """,
            (
                project_uuid,
                project.draft.version,
                Jsonb(_script_to_json(project.draft.script)),
                Jsonb([_scene_to_json(scene) for scene in project.draft.storyboard]),
                project.draft.updated_at,
            ),
        )
