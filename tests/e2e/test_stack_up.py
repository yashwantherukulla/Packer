import httpx
import pytest

pytestmark = pytest.mark.e2e


def test_openapi_and_docs_served(api_client: httpx.Client):
    assert api_client.get("/openapi.json").status_code == 200
    assert api_client.get("/docs").status_code == 200


def test_frontend_root_served(compose_stack: str):
    from tests.e2e.conftest import FRONTEND_BASE

    assert httpx.get(FRONTEND_BASE, timeout=10).status_code == 200
