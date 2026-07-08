from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from packer.api import deps
from packer.api.jobs.service import JobService

router = APIRouter()


@router.websocket("/ws/jobs/{job_id}")
async def ws_jobs(
    ws: WebSocket,
    job_id: str,
    hub: Any = Depends(deps.get_hub),
    svc: JobService = Depends(deps.get_job_service),
) -> None:
    await ws.accept()
    job = svc.get(job_id)  # reconcile: push current state on connect
    if job is not None:
        await ws.send_json(job.model_dump(mode="json"))
    try:
        await hub.relay(job_id, ws.send_text)
    except WebSocketDisconnect:
        return
