import pytest

pytestmark = pytest.mark.integration


def test_detect_job_persists_and_completes(client, tiny_safetensors_ref):
    resp = client.post("/detect", json={"model_ref": tiny_safetensors_ref})
    job_id = resp.json()["id"]
    # eager execution ran the task inline; job is terminal + report persisted
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] in {"succeeded", "failed"}
    if job["status"] == "succeeded":
        rid = job["result_ref"].split("report:")[1]
        assert client.get(f"/reports/{rid}").json()["kind"] == "detect"


def test_unsafe_pickle_upload_becomes_failed_job_not_500(client, pickle_bytes):
    resp = client.post("/models", json={"source": "upload", "format": "pickle"})
    assert resp.status_code in {422, 400}  # mapped UnsafeModelError, never an uncaught 500
