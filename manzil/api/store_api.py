"""Store, perception, analytics and export endpoints (W5; G03, G05, FR-18, FR-19).

::

    GET  /api/store/summary              tables, counts and studies in the store
    POST /api/store/import               re-import results/ and runs/live/ (idempotent)
    GET  /api/runs?study=&arm=&...       run list (filters: study source controller profile
                                         status label arm scenario seed)
    GET  /api/runs/{run_key}             one run: config, metrics, missions, files
    POST /api/compare                    {run_keys, group_by, metrics?, reference?} -> FR-18
    POST /api/export                     {run_keys, format: json|csv} -> file download (FR-19)
    GET  /api/perception/jobs            prepared video jobs (G03)
    GET  /api/perception/jobs/{job_id}   one job: provenance, summary, artifacts
    GET  /api/perception/jobs/{job_id}/observations?name=
    GET  /api/files/{path}               a committed result image listed as an artifact
"""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from manzil.experiments.runner import REPO_ROOT
from manzil.store.analytics import GROUP_FIELDS, compare_runs
from manzil.store.export import build_export, to_csv
from manzil.store.importer import import_all
from manzil.store.repository import ExperimentRepository


class CompareRequest(BaseModel):
    run_keys: list[str] = Field(..., min_length=1, max_length=2000)
    group_by: str = "arm"
    metrics: list[str] | None = None
    reference: str | None = None


class ExportRequest(BaseModel):
    run_keys: list[str] = Field(..., min_length=1, max_length=2000)
    format: Literal["json", "csv"] = "json"


def store_router(repo: ExperimentRepository) -> APIRouter:
    r = APIRouter(prefix="/api")

    @r.get("/store/summary")
    def summary():
        return repo.summary()

    @r.post("/store/import")
    def reimport():
        return import_all(repo, REPO_ROOT)

    @r.get("/runs")
    def runs(
        study: str | None = None,
        source: str | None = None,
        controller: str | None = None,
        profile: str | None = None,
        status: str | None = None,
        label: str | None = None,
        arm: str | None = None,
        scenario: str | None = None,
        seed: int | None = None,
    ):
        return repo.list_runs(
            study=study,
            source=source,
            controller=controller,
            profile=profile,
            status=status,
            label=label,
            arm=arm,
            scenario=scenario,
            seed=seed,
        )

    @r.get("/runs/{run_key:path}")
    def run(run_key: str):
        out = repo.get_run(run_key)
        if out is None:
            raise HTTPException(404, f"unknown run {run_key!r}")
        return out

    @r.post("/compare")
    def compare(req: CompareRequest):
        if req.group_by not in GROUP_FIELDS:
            raise HTTPException(422, f"group_by must be one of {GROUP_FIELDS}")
        try:
            return compare_runs(repo, req.run_keys, req.group_by, req.metrics, req.reference)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

    @r.post("/export")
    def export(req: ExportRequest):
        try:
            if req.format == "csv":
                body, media = to_csv(repo, req.run_keys), "text/csv"
            else:
                body = json.dumps(build_export(repo, req.run_keys), indent=2, allow_nan=False)
                media = "application/json"
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        name = f"manzil_export_{len(req.run_keys)}runs.{req.format}"
        return Response(
            body,
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @r.get("/perception/jobs")
    def jobs():
        return repo.list_video_jobs()

    @r.get("/perception/jobs/{job_id:path}/observations")
    def observations(job_id: str, name: str | None = Query(None)):
        if repo.get_video_job(job_id) is None:
            raise HTTPException(404, f"unknown video job {job_id!r}")
        return repo.observations(job_id, name)

    @r.get("/perception/jobs/{job_id:path}")
    def job(job_id: str):
        out = repo.get_video_job(job_id)
        if out is None:
            raise HTTPException(404, f"unknown video job {job_id!r}")
        return out

    @r.get("/files/{path:path}")
    def files(path: str):
        """Only images that the store lists as artifacts, so no other file can be read."""
        allowed = {
            a["uri"]
            for j in repo.list_video_jobs()
            for a in (repo.get_video_job(j["job_id"]) or {}).get("artifacts", [])
        }
        p = (REPO_ROOT / path).resolve()
        if path not in allowed or not p.is_file() or p.suffix not in (".png", ".jpg", ".mp4"):
            raise HTTPException(404, "not a listed result file")
        return FileResponse(p)

    return r
