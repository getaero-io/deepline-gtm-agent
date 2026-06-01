from pathlib import Path

from fastapi.testclient import TestClient


def test_managed_server_uses_native_deepline_stream():
    source = Path("managed_agent/server.py").read_text()

    assert "DeeplineV2Client" in source
    assert "/api/v2/integrations/deeplineagent/stream" not in source
    assert "BOOTSTRAP_MSG" not in source
    assert "create_session(" not in source
    assert "stream_events(" not in source


def test_root_server_delegates_to_v2_broker():
    source = Path("server.py").read_text()

    assert "from managed_agent.server import app" in source
    assert "create_gtm_agent" not in source
    assert "load_tool_catalog" not in source


def test_managed_agent_does_not_upload_cli_or_auth_files():
    combined = "\n".join(
        Path(path).read_text()
        for path in [
            "managed_agent/session.py",
            "managed_agent/setup.py",
            "managed_agent/Dockerfile",
            "railway.toml",
        ]
    )

    assert "deepline-auth.env" not in combined
    assert "/mnt/session/uploads/workspace/deepline" not in combined
    assert "zipapp" not in combined
    assert "NODE_TLS_REJECT_UNAUTHORIZED=0" not in combined


def test_health_fails_when_deepline_key_missing(monkeypatch):
    monkeypatch.delenv("DEEPLINE_API_KEY", raising=False)

    from managed_agent.server import app

    response = TestClient(app).get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "needs setup"


def test_slack_signature_fails_closed_without_secret(monkeypatch):
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)

    import managed_agent.server as server
    monkeypatch.setattr(server, "SLACK_SIGNING_SECRET", "")

    assert server._verify_slack_sig(b"{}", "1", "v0=fake") is False
