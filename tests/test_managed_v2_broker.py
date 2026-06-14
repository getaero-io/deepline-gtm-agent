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


def test_bulk_prospect_requests_get_native_v2_list_guidance():
    from managed_agent.server import ChatRequest, _chat_payload

    payload = _chat_payload(
        ChatRequest(
            message="Build a CSV prospect list of 20 VP Engineering contacts at AI infrastructure companies."
        )
    )

    assert payload["prompt"].startswith("Bulk prospect/list requests")
    assert "native v2 list-building workflow" in payload["prompt"]
    assert "Production GTM agent requests must use this operating loop" in payload["prompt"]
    assert "pilot/sample first" in payload["messages"][0]["content"]
    assert payload["messages"][0]["role"] == "user"


def test_one_off_prospect_requests_do_not_get_bulk_guidance():
    from managed_agent.server import ChatRequest, _chat_payload

    payload = _chat_payload(ChatRequest(message="Find the LinkedIn URL for Jensen Huang at NVIDIA."))

    assert payload["prompt"] == "Find the LinkedIn URL for Jensen Huang at NVIDIA."
    assert payload["messages"][0]["role"] == "user"
    assert "native v2 list-building workflow" not in payload["messages"][0]["content"]


def test_agent_workflow_requests_get_production_operating_loop():
    from managed_agent.server import ChatRequest, _chat_payload

    payload = _chat_payload(
        ChatRequest(
            message=(
                "Build a GTM agent that researches accounts, drafts outreach, "
                "asks for approval, and writes approved updates back to Salesforce."
            )
        )
    )

    content = payload["messages"][0]["content"]
    assert content.startswith("Production GTM agent requests must use this operating loop")
    assert "Approval gate" in content
    assert "Write back" in content
    assert "LangChain: approval loops" in content
    assert "Exa: search should return workflow-ready context" in content
    assert "Composio: tool use needs auth" in content
    assert "AssemblyAI: voice/conversation agents" in content


def test_legacy_prompt_contains_event_agent_patterns():
    from deepline_gtm_agent.prompts import GTM_SYSTEM_PROMPT

    assert "Production GTM agent loop" in GTM_SYSTEM_PROMPT
    assert "LangChain: approval loops" in GTM_SYSTEM_PROMPT
    assert "Exa: search returns workflow-ready context" in GTM_SYSTEM_PROMPT
    assert "Composio: tool use needs auth" in GTM_SYSTEM_PROMPT
    assert "AssemblyAI: voice/conversation agents" in GTM_SYSTEM_PROMPT


def test_workflow_presets_are_discoverable(monkeypatch):
    monkeypatch.delenv("DEEPLINE_API_KEY", raising=False)

    from managed_agent.server import app

    response = TestClient(app).get("/workflow-presets")

    assert response.status_code == 200
    presets = response.json()["presets"]
    preset_ids = {preset["id"] for preset in presets}
    assert {
        "inbound_lead_approval",
        "account_digest",
        "self_serve_support_agent",
        "web_context_research",
        "bounded_tool_action",
        "closed_loop_gtm_workflow",
    }.issubset(preset_ids)


def test_workflow_preset_includes_prompt_tool_bounds_and_output_shape(monkeypatch):
    monkeypatch.delenv("DEEPLINE_API_KEY", raising=False)

    from managed_agent.server import app

    response = TestClient(app).get("/workflow-presets/web_context_research")

    assert response.status_code == 200
    preset = response.json()
    assert preset["speaker_pattern"] == "Exa / Scott Langille"
    assert "prompt" in preset
    assert "suggested_tool_bounds" in preset
    assert "expected_output" in preset
    assert "source-backed claims" in preset["expected_output"]
    assert preset["suggested_tool_bounds"]["maxToolCalls"] == 6


def test_unknown_workflow_preset_404s(monkeypatch):
    monkeypatch.delenv("DEEPLINE_API_KEY", raising=False)

    from managed_agent.server import app

    response = TestClient(app).get("/workflow-presets/nope")

    assert response.status_code == 404
