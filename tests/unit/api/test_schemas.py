import pytest
from pydantic import ValidationError

from packer.api.db.models import Job
from packer.api.schemas.requests import DetectRequest, ScanRequest
from packer.api.schemas.responses import JobRecord


def test_detect_request_requires_model_ref():
    assert DetectRequest(model_ref="Qwen/Qwen2.5-0.5B").model_ref
    with pytest.raises(ValidationError):
        DetectRequest()  # type: ignore[call-arg]


def test_scan_request_accepts_extraction_or_model_ref():
    assert ScanRequest(model_ref="x").model_ref == "x"
    assert ScanRequest(extraction_id="e1").extraction_id == "e1"
    with pytest.raises(ValidationError):
        ScanRequest()  # exactly one of the two required


def test_job_record_maps_from_orm_row():
    row = Job(
        id="j1",
        type="pack",
        status="succeeded",
        correlation_id="j1",
        result_ref="artifact:a1",
        progress_pct=1.0,
    )
    rec = JobRecord.model_validate(row, from_attributes=True)
    assert rec.id == "j1" and rec.status == "succeeded" and rec.result_ref == "artifact:a1"
