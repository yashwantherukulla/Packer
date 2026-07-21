from tests.unit.fakes import InMemoryJobRepository

from packer.api.jobs.service import JobService


def test_create_returns_queued_job_with_correlation_id():
    svc = JobService(InMemoryJobRepository())
    job = svc.create(type="detect", input_ref="Qwen/x")
    assert job.status == "queued" and job.correlation_id == job.id and job.type == "detect"


def test_dedup_returns_existing_succeeded_job():
    repo = InMemoryJobRepository()
    svc = JobService(repo, dedup=True)
    first = svc.create(type="pack", input_ref="u/1", input_hash="h1")
    repo.mark_succeeded(first.id, result_ref="artifact:a1")
    again = svc.create(type="pack", input_ref="u/1", input_hash="h1")
    assert again.id == first.id  # reused, not recomputed


def test_dedup_off_always_creates():
    repo = InMemoryJobRepository()
    svc = JobService(repo, dedup=False)
    a = svc.create(type="pack", input_hash="h1")
    repo.mark_succeeded(a.id, result_ref="artifact:a1")
    b = svc.create(type="pack", input_hash="h1")
    assert b.id != a.id


def test_non_digest_input_hash_is_normalized_before_storage_and_lookup():
    repo = InMemoryJobRepository()
    svc = JobService(repo, dedup=True)
    model_ref = "/tmp/pytest-of-runner/pytest-0/test_detect_job_persists_and_c0/tiny_model"
    first = svc.create(type="detect", input_ref=model_ref, input_hash=model_ref)
    stored = repo.get(first.id)
    assert stored is not None
    assert stored.input_hash != model_ref
    assert len(stored.input_hash or "") == 64
    repo.mark_succeeded(first.id, result_ref="report:r1")
    again = svc.create(type="detect", input_ref=model_ref, input_hash=model_ref)
    assert again.id == first.id
