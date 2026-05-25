"""
Tests for deepline_gtm_agent.dynamic_tools — catalog loading and deepline_call tool.
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

for mod in ["deepagents", "langchain_core", "langchain_core.tools"]:
    sys.modules.setdefault(mod, MagicMock())

# Stub pydantic
pydantic_mock = MagicMock()
pydantic_mock.BaseModel = object
pydantic_mock.Field = lambda *a, **kw: None
sys.modules.setdefault("pydantic", pydantic_mock)

from deepline_gtm_agent.dynamic_tools import (
    _build_catalog_text,
    _fetch_catalog_from_api,
    _fetch_catalog_from_cli,
    _load_catalog_cache,
    _save_catalog_cache,
    load_tool_catalog,
    make_deepline_call_tool,
    CATALOG_TTL_SECONDS,
)


SAMPLE_TOOLS = [
    {"toolId": "hunter_email_finder", "provider": "hunter", "categories": ["email_finder"],
     "description": "Find email by domain and name"},
    {"toolId": "hubspot_create_contact", "provider": "hubspot", "categories": ["admin"],
     "description": "Create a HubSpot contact"},
    {"toolId": "apollo_search_people", "provider": "apollo", "categories": ["people_search"],
     "description": "Search for people on Apollo"},
    {"toolId": "read_file", "provider": "local", "categories": ["admin"],
     "description": "Read a local file"},  # should be skipped
]


# ---------------------------------------------------------------------------
# Catalog cache
# ---------------------------------------------------------------------------

class TestCatalogCache:
    def test_save_and_load_cache(self, tmp_path):
        cache_path = tmp_path / "catalog.json"
        with patch("deepline_gtm_agent.dynamic_tools.CATALOG_CACHE_PATH", cache_path):
            _save_catalog_cache(SAMPLE_TOOLS[:2])
            result = _load_catalog_cache()
            assert result is not None
            assert len(result) == 2

    def test_stale_cache_returns_none(self, tmp_path):
        cache_path = tmp_path / "catalog.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        # Write cache with old timestamp
        cache_path.write_text(json.dumps({
            "cached_at": time.time() - CATALOG_TTL_SECONDS - 1,
            "tools": SAMPLE_TOOLS[:2],
        }))
        with patch("deepline_gtm_agent.dynamic_tools.CATALOG_CACHE_PATH", cache_path):
            result = _load_catalog_cache()
            assert result is None

    def test_missing_cache_returns_none(self, tmp_path):
        cache_path = tmp_path / "nonexistent.json"
        with patch("deepline_gtm_agent.dynamic_tools.CATALOG_CACHE_PATH", cache_path):
            result = _load_catalog_cache()
            assert result is None

    def test_corrupt_cache_returns_none(self, tmp_path):
        cache_path = tmp_path / "catalog.json"
        cache_path.write_text("not json{")
        with patch("deepline_gtm_agent.dynamic_tools.CATALOG_CACHE_PATH", cache_path):
            result = _load_catalog_cache()
            assert result is None


# ---------------------------------------------------------------------------
# CLI catalog fetch
# ---------------------------------------------------------------------------

class TestFetchCatalogFromCLI:
    def test_parses_tools_key(self):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"tools": SAMPLE_TOOLS}))
        with patch("deepline_gtm_agent.dynamic_tools.subprocess.run", return_value=mock_result):
            result = _fetch_catalog_from_cli()
            assert result == SAMPLE_TOOLS

    def test_parses_integrations_key(self):
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"integrations": SAMPLE_TOOLS[:2]}))
        with patch("deepline_gtm_agent.dynamic_tools.subprocess.run", return_value=mock_result):
            result = _fetch_catalog_from_cli()
            assert len(result) == 2

    def test_nonzero_exit_returns_empty(self):
        mock_result = MagicMock(returncode=1, stdout="")
        with patch("deepline_gtm_agent.dynamic_tools.subprocess.run", return_value=mock_result):
            result = _fetch_catalog_from_cli()
            assert result == []

    def test_exception_returns_empty(self):
        with patch("deepline_gtm_agent.dynamic_tools.subprocess.run",
                   side_effect=FileNotFoundError):
            result = _fetch_catalog_from_cli()
            assert result == []


# ---------------------------------------------------------------------------
# load_tool_catalog — skip list
# ---------------------------------------------------------------------------

class TestLoadToolCatalog:
    def test_local_only_tools_excluded(self, tmp_path):
        """read_file and call_local_* tools should never appear in catalog."""
        cache_path = tmp_path / "catalog.json"
        mock_result = MagicMock(returncode=0, stdout=json.dumps({"tools": SAMPLE_TOOLS}))
        with patch("deepline_gtm_agent.dynamic_tools.CATALOG_CACHE_PATH", cache_path), \
             patch("deepline_gtm_agent.dynamic_tools.subprocess.run", return_value=mock_result), \
             patch("deepline_gtm_agent.dynamic_tools.os.environ.get", return_value=""):
            result = load_tool_catalog(force_refresh=True)
            tool_ids = [t["toolId"] for t in result]
            assert "read_file" not in tool_ids
            assert "call_local_claude_code" not in tool_ids

    def test_uses_cache_when_fresh(self, tmp_path):
        cache_path = tmp_path / "catalog.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({
            "cached_at": time.time(),
            "tools": SAMPLE_TOOLS[:2],
        }))
        with patch("deepline_gtm_agent.dynamic_tools.CATALOG_CACHE_PATH", cache_path):
            result = load_tool_catalog(force_refresh=False)
            assert len(result) == 2


# ---------------------------------------------------------------------------
# _build_catalog_text
# ---------------------------------------------------------------------------

class TestBuildCatalogText:
    def test_all_tools_appear(self):
        tools = [
            {"toolId": "hunter_email_finder", "provider": "hunter", "categories": ["email_finder"],
             "description": "Find email"},
            {"toolId": "hubspot_create_contact", "provider": "hubspot", "categories": ["admin"],
             "description": "Create contact"},
        ]
        text = _build_catalog_text(tools)
        assert "hunter_email_finder" in text
        assert "hubspot_create_contact" in text

    def test_priority_providers_listed_first(self):
        """hubspot (priority) should appear before unknown provider."""
        tools = [
            {"toolId": "unknown_tool", "provider": "unknown_provider", "categories": ["admin"],
             "description": "Some tool"},
            {"toolId": "hubspot_create_contact", "provider": "hubspot", "categories": ["admin"],
             "description": "Create contact"},
        ]
        text = _build_catalog_text(tools)
        assert text.index("hubspot_create_contact") < text.index("unknown_tool")

    def test_long_description_truncated(self):
        tools = [{"toolId": "test_tool", "provider": "test", "categories": ["admin"],
                  "description": "x" * 200}]
        text = _build_catalog_text(tools)
        assert "…" in text

    def test_empty_catalog_returns_string(self):
        text = _build_catalog_text([])
        assert isinstance(text, str)

    def test_category_headers_present(self):
        tools = [
            {"toolId": "hunter_email_finder", "provider": "hunter", "categories": ["email_finder"],
             "description": "Find email"},
        ]
        text = _build_catalog_text(tools)
        assert "Email Finder" in text or "email_finder" in text.lower()


# ---------------------------------------------------------------------------
# make_deepline_call_tool
# ---------------------------------------------------------------------------

class _FakeTool:
    """Lightweight StructuredTool substitute that captures constructor kwargs."""
    def __init__(self, **kwargs):
        self.name = kwargs.get("name")
        self.description = kwargs.get("description", "")
        self.func = kwargs.get("func")


class TestMakeDeeplineCallTool:
    """Tests for make_deepline_call_tool.

    StructuredTool from langchain_core is stubbed by conftest, so we patch it
    locally with _FakeTool to capture the constructor kwargs and inner func.
    """

    def test_tool_has_correct_name(self):
        with patch("deepline_gtm_agent.dynamic_tools.StructuredTool", _FakeTool):
            tool = make_deepline_call_tool(SAMPLE_TOOLS[:2])
        assert tool.name == "deepline_call"

    def test_tool_description_contains_catalog(self):
        with patch("deepline_gtm_agent.dynamic_tools.StructuredTool", _FakeTool):
            tool = make_deepline_call_tool(SAMPLE_TOOLS[:2])
        assert "hunter_email_finder" in tool.description

    def test_successful_call_returns_result(self):
        mock_result = {"email": "jane@acme.com"}
        with patch("deepline_gtm_agent.dynamic_tools.StructuredTool", _FakeTool):
            with patch("deepline_gtm_agent.dynamic_tools.deepline_execute", return_value=mock_result):
                tool = make_deepline_call_tool(SAMPLE_TOOLS[:2])
                result = tool.func("hunter_email_finder", {"domain": "acme.com"})
        assert result == mock_result

    def test_credentials_missing_returns_friendly_message(self):
        error_body = json.dumps({
            "code": "INTEGRATION_CREDENTIALS_MISSING",
            "integration_provider": "hubspot",
        })
        with patch("deepline_gtm_agent.dynamic_tools.StructuredTool", _FakeTool):
            with patch("deepline_gtm_agent.dynamic_tools.deepline_execute",
                       side_effect=Exception(f"Bad request: {error_body}")):
                tool = make_deepline_call_tool([])
                result = tool.func("hubspot_create_contact", {})
        assert isinstance(result, str)
        assert "CREDENTIALS_MISSING" in result
        assert "hubspot" in result.lower()
        assert "code.deepline.com" in result

    def test_generic_error_returns_error_dict(self):
        with patch("deepline_gtm_agent.dynamic_tools.StructuredTool", _FakeTool):
            with patch("deepline_gtm_agent.dynamic_tools.deepline_execute",
                       side_effect=Exception("network timeout")):
                tool = make_deepline_call_tool([])
                result = tool.func("some_tool", {})
        assert isinstance(result, dict)
        assert "error" in result

    def test_none_payload_defaults_to_empty_dict(self):
        with patch("deepline_gtm_agent.dynamic_tools.StructuredTool", _FakeTool):
            with patch("deepline_gtm_agent.dynamic_tools.deepline_execute",
                       return_value={"ok": True}) as mock_exec:
                tool = make_deepline_call_tool([])
                tool.func("some_tool", None)
        assert mock_exec.call_args[0][1] == {}

    def test_empty_catalog_still_creates_tool(self):
        with patch("deepline_gtm_agent.dynamic_tools.StructuredTool", _FakeTool):
            tool = make_deepline_call_tool([])
        assert tool.name == "deepline_call"
        assert "catalog unavailable" in tool.description
