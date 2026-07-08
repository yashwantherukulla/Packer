import pytest

pytestmark = pytest.mark.integration


def test_pack_then_detect_then_report(client, tiny_repo_zip):
    # POST /pack (tiny fixture) -> poll /jobs -> GET /artifacts
    packed = client.post("/pack", files={"file": ("repo.zip", tiny_repo_zip, "application/zip")})
    pack_job = _poll(client, packed.json()["id"])
    assert pack_job["status"] == "succeeded"
    artifact_id = pack_job["result_ref"].split("artifact:")[1]
    art = client.get(f"/artifacts/{artifact_id}").json()
    assert art["metrics_json"]["lossless"] is True

    # POST /detect on that artifact -> GET /reports
    det = client.post("/detect", json={"model_ref": artifact_id})
    det_job = _poll(client, det.json()["id"])
    report_id = det_job["result_ref"].split("report:")[1]
    report = client.get(f"/reports/{report_id}").json()
    assert report["kind"] == "detect"


def _poll(client, job_id, tries=60):
    import time

    for _ in range(tries):
        job = client.get(f"/jobs/{job_id}").json()
        if job["status"] in {"succeeded", "failed"}:
            return job
        time.sleep(0.5)
    raise AssertionError("job did not finish")
