"""
Tests for managed_agent/session.py — session creation and event streaming.
"""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Load session.py directly without installing the package
def load_session_module():
    spec = importlib.util.spec_from_file_location(
        "managed_agent_session",
        "/tmp/deepline-gtm-agent-fix/managed_agent/session.py",
    )
    mod = importlib.util.module_from_spec(spec)
    # Inject mocked anthropic before exec
    anthropic_mock = MagicMock()
    mod.__builtins__ = __builtins__
    sys.modules["anthropic"] = anthropic_mock
    sys.modules["httpx"] = MagicMock()
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def session_mod():
    return load_session_module()


# ---------------------------------------------------------------------------
# BOOTSTRAP_MSG
# ---------------------------------------------------------------------------

class TestBootstrapMsg:
    def test_bootstrap_exists(self, session_mod):
        assert hasattr(session_mod, "BOOTSTRAP_MSG")
        assert len(session_mod.BOOTSTRAP_MSG) > 100

    def test_bootstrap_installs_cli(self, session_mod):
        assert "~/.local/bin/deepline" in session_mod.BOOTSTRAP_MSG or "deepline" in session_mod.BOOTSTRAP_MSG

    def test_bootstrap_patches_proxy(self, session_mod):
        assert "urllib" in session_mod.BOOTSTRAP_MSG or "proxy" in session_mod.BOOTSTRAP_MSG.lower()

    def test_bootstrap_fixes_dns(self, session_mod):
        assert "/etc/hosts" in session_mod.BOOTSTRAP_MSG or "DNS" in session_mod.BOOTSTRAP_MSG

    def test_bootstrap_sets_node_options(self, session_mod):
        assert "NODE_OPTIONS" in session_mod.BOOTSTRAP_MSG

    def test_bootstrap_silent_instruction(self, session_mod):
        """Bootstrap should instruct agent to run silently."""
        text = session_mod.BOOTSTRAP_MSG.lower()
        assert "silently" in text or "do not output" in text

    def test_bootstrap_creates_deepline_data_dir(self, session_mod):
        """Bootstrap should create ~/deepline/data/ for working directory policy."""
        assert "deepline/data" in session_mod.BOOTSTRAP_MSG


# ---------------------------------------------------------------------------
# fetch_skill_docs_from_cdn
# ---------------------------------------------------------------------------

class TestFetchSkillDocsFromCdn:
    def test_returns_dict(self, session_mod):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"# SKILL content"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = MagicMock(return_value=mock_resp)
        with patch("httpx.Client", return_value=mock_client):
            # Reset cache
            session_mod._cached_skill_files = {}
            result = session_mod.fetch_skill_docs_from_cdn()
            assert isinstance(result, dict)

    def test_caches_on_second_call(self, session_mod):
        """Second call should return cached result without HTTP requests."""
        cached_data = {"SKILL.md": b"content"}
        session_mod._cached_skill_files = cached_data
        with patch("httpx.Client") as mock_http:
            result = session_mod.fetch_skill_docs_from_cdn()
            assert result == cached_data
            mock_http.assert_not_called()
        # Reset
        session_mod._cached_skill_files = {}

    def test_404_docs_excluded(self, session_mod):
        """Docs that return non-200 should be excluded from result."""
        def mock_get(url):
            resp = MagicMock()
            resp.status_code = 404
            resp.content = b""
            return resp
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = mock_get
        with patch("httpx.Client", return_value=mock_client):
            session_mod._cached_skill_files = {}
            result = session_mod.fetch_skill_docs_from_cdn()
            assert len(result) == 0


# ---------------------------------------------------------------------------
# _parse_event
# ---------------------------------------------------------------------------

class TestParseEvent:
    def test_agent_message_text_event(self, session_mod):
        event = MagicMock()
        event.type = "agent.message"
        block = MagicMock()
        block.type = "text"
        block.text = "Hello world"
        event.content = [block]
        result = session_mod._parse_event(event)
        assert result == {"type": "text", "text": "Hello world"}

    def test_agent_tool_use_bash(self, session_mod):
        event = MagicMock()
        event.type = "agent.tool_use"
        event.name = "bash"
        event.input = {"command": "deepline enrich --input leads.csv"}
        result = session_mod._parse_event(event)
        assert result["type"] == "tool"
        assert result["name"] == "bash"
        assert "deepline enrich" in result["command"]

    def test_agent_tool_use_non_bash(self, session_mod):
        event = MagicMock()
        event.type = "agent.tool_use"
        event.name = "some_tool"
        event.input = {}
        result = session_mod._parse_event(event)
        assert result == {"type": "tool", "name": "some_tool"}

    def test_session_idle_returns_done(self, session_mod):
        event = MagicMock()
        event.type = "session.status_idle"
        stop_reason = MagicMock()
        stop_reason.type = "end_turn"
        event.stop_reason = stop_reason
        result = session_mod._parse_event(event)
        assert result == {"type": "done", "reason": "end_turn"}

    def test_session_idle_requires_action_returns_none(self, session_mod):
        """Transient idle (requires_action) should be skipped."""
        event = MagicMock()
        event.type = "session.status_idle"
        stop_reason = MagicMock()
        stop_reason.type = "requires_action"
        event.stop_reason = stop_reason
        result = session_mod._parse_event(event)
        assert result is None

    def test_session_terminated_returns_done(self, session_mod):
        event = MagicMock()
        event.type = "session.status_terminated"
        result = session_mod._parse_event(event)
        assert result == {"type": "done", "reason": "terminated"}

    def test_unknown_event_returns_none(self, session_mod):
        event = MagicMock()
        event.type = "unknown.event.type"
        result = session_mod._parse_event(event)
        assert result is None

    def test_agent_message_non_text_block_returns_none(self, session_mod):
        event = MagicMock()
        event.type = "agent.message"
        block = MagicMock()
        block.type = "image"  # not text
        event.content = [block]
        result = session_mod._parse_event(event)
        assert result is None


# ---------------------------------------------------------------------------
# _load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_loads_from_env_vars(self, session_mod, monkeypatch):
        monkeypatch.setenv("MANAGED_AGENT_ID", "agt_test_123")
        monkeypatch.setenv("MANAGED_ENVIRONMENT_ID", "env_test_456")
        config = session_mod._load_config()
        assert config["agent_id"] == "agt_test_123"
        assert config["environment_id"] == "env_test_456"

    def test_env_vars_take_precedence_over_file(self, session_mod, monkeypatch, tmp_path):
        monkeypatch.setenv("MANAGED_AGENT_ID", "env_agent")
        monkeypatch.setenv("MANAGED_ENVIRONMENT_ID", "env_environment")
        # File exists but env should win
        config_path = tmp_path / ".agent_config.json"
        config_path.write_text(json.dumps({"agent_id": "file_agent", "environment_id": "file_env"}))
        with patch.object(session_mod, "CONFIG_PATH", config_path):
            config = session_mod._load_config()
            assert config["agent_id"] == "env_agent"

    def test_raises_when_no_config(self, session_mod, monkeypatch, tmp_path):
        monkeypatch.delenv("MANAGED_AGENT_ID", raising=False)
        monkeypatch.delenv("MANAGED_ENVIRONMENT_ID", raising=False)
        missing_path = tmp_path / "missing.json"
        with patch.object(session_mod, "CONFIG_PATH", missing_path):
            with pytest.raises(FileNotFoundError):
                session_mod._load_config()

    def test_loads_from_json_file(self, session_mod, monkeypatch, tmp_path):
        monkeypatch.delenv("MANAGED_AGENT_ID", raising=False)
        monkeypatch.delenv("MANAGED_ENVIRONMENT_ID", raising=False)
        config_path = tmp_path / ".agent_config.json"
        config_path.write_text(json.dumps({"agent_id": "agt_file", "environment_id": "env_file"}))
        with patch.object(session_mod, "CONFIG_PATH", config_path):
            config = session_mod._load_config()
            assert config["agent_id"] == "agt_file"
