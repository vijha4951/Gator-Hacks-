import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import Settings


@pytest.mark.parametrize("origin,expected", [
    ("https://circuitgaurd.vercel.app",200),
    ("https://circuitgaurd-new123-gatorhacks-vivi.vercel.app",200),
    ("https://circuitgaurd-git-frontend-gatorhacks-vivi.vercel.app",200),
    ("https://unrelated.vercel.app",400),
    ("https://circuitgaurd-new123-other-team.vercel.app",400),
    ("https://circuitgaurd-new123-gatorhacks-vivi.vercel.app.evil.example",400),
])
def test_project_cors_preflight(origin,expected):
    with TestClient(app) as client:
        r=client.options("/api/analyze",headers={
            "Origin":origin,"Access-Control-Request-Method":"POST",
            "Access-Control-Request-Headers":"content-type",
        })
    assert r.status_code==expected
    if expected==200:
        assert r.headers["access-control-allow-origin"]==origin
    else:
        assert "access-control-allow-origin" not in r.headers


def test_deployment_defaults_do_not_require_local_env(monkeypatch):
    import re
    monkeypatch.delenv("CORS_ORIGINS",raising=False)
    monkeypatch.delenv("CORS_ORIGIN_REGEX",raising=False)
    settings=Settings(_env_file=None)
    assert "https://circuitgaurd.vercel.app" in settings.cors_origins
    assert re.fullmatch(settings.cors_origin_regex,
                        "https://circuitgaurd-next123-gatorhacks-vivi.vercel.app")
