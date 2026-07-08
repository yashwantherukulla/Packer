from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any, cast

from packer.api.repos import ArtifactRepository, JobRepository, ReportRepository
from packer.engine.common.assembler import EnginePorts
from packer.engine.common.errors import PackerError
from packer.engine.common.logging import bind_correlation_id, get_logger
from packer.engine.common.progress import ProgressCallback
from packer.engine.report.model import Report
from packer.workers.progress import RedisProgress

_log = get_logger("packer.workers.runner")

# ports is `Any` (not `EnginePorts`) so the engine-call lambdas can pass the wired
# ports straight into engines whose signatures declare their own structural port
# Protocols; the return is `object` to also cover the extract path's `Extraction`.
EngineCall = Callable[[Any, ProgressCallback], object]


def run_engine_job(
    job_id: str,
    engine_call: EngineCall,
    *,
    jobs: JobRepository,
    reports: ReportRepository,
    artifacts: ArtifactRepository,
    ports: EnginePorts,
    redis_client: Any,
) -> None:
    """The ONE job-lifecycle wrapper (SYSTEM-DESIGN §5.7). Written once; the four
    Celery tasks differ only by the engine_call they pass."""
    bind_correlation_id(job_id)
    job = jobs.get(job_id)
    if job is None:
        raise PackerError(f"job not found: {job_id}", context={"job_id": job_id})
    jobs.mark_running(job_id)
    progress = RedisProgress(job_id, redis_client)
    try:
        result = engine_call(ports, progress)
        ref = _persist_result(job, result, ports=ports, artifacts=artifacts, reports=reports)
        jobs.mark_succeeded(job_id, result_ref=ref)
    except PackerError as exc:
        jobs.mark_failed(job_id, code=exc.code, msg=str(exc))  # engine error -> failed job
    except Exception as exc:  # unknown -> fail loudly + surface
        jobs.mark_failed(job_id, code="internal", msg=str(exc))
        _log.exception("job %s crashed", job_id)
        raise


def _persist_result(
    job: Any,
    result: object,
    *,
    ports: EnginePorts,
    artifacts: ArtifactRepository,
    reports: ReportRepository,
) -> str:
    if isinstance(result, Report):
        rid = uuid.uuid4().hex
        reports.insert(
            id=rid, job_id=job.id, kind=result.kind, report=result.model_dump(mode="json")
        )
        return f"report:{rid}"
    # str result = opaque store reference (pack artifact id | extraction id)
    if job.type == "pack" and isinstance(result, str):
        store = cast(Any, ports.store)
        bundle = store.open_pak(result)
        artifacts.insert(
            id=result,
            job_id=job.id,
            pak_path=result,
            manifest=bundle.manifest.model_dump(mode="json"),
            metrics=bundle.manifest.metrics.model_dump(mode="json"),
        )
        return f"artifact:{result}"
    return f"extraction:{result}"
