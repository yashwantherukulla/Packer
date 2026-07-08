from fastapi import FastAPI
from fastapi.testclient import TestClient

from packer.api.errors import code_to_status, register_error_handlers
from packer.engine.common.errors import UnsafeModelError


def test_code_to_status_mapping():
    assert code_to_status("unsafe_model") == 422
    assert code_to_status("config_error") == 400
    assert code_to_status("something_unknown") == 500


def test_handler_renders_problem_json():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise UnsafeModelError("pickle without opt-in")

    resp = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "unsafe_model" and body["status"] == 422
    assert "pickle" in body["detail"]
