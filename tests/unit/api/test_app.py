from fastapi.testclient import TestClient

from packer.api.main import create_app


def test_app_boots_and_health_ok():
    app = create_app()
    with TestClient(app) as client:  # enters lifespan; pools are lazy, need no live DB/Redis
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_settings_loaded_via_hydra():
    app = create_app()
    assert app.state.settings.api.port == 8000
    assert app.state.settings.broker.progress_prefix == "progress:"
