"""
Tests for deepline_gtm_agent.skills — CDN skill doc loading.
"""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

for mod in ["deepagents", "langchain_core", "langchain_core.tools"]:
    sys.modules.setdefault(mod, MagicMock())

from deepline_gtm_agent.skills import (
    CORE_SKILL_DOCS,
    LOCAL_SKILL_DOCS,
    SKILLS_BASE,
    load_skill_docs,
    load_skill_docs_sync,
)


# ---------------------------------------------------------------------------
# Skill doc list coverage
# ---------------------------------------------------------------------------

class TestCoreSkillDocList:
    def test_skill_md_is_included(self):
        paths = [path for path, _ in CORE_SKILL_DOCS]
        assert "SKILL.md" in paths

    def test_phase_docs_included(self):
        paths = [path for path, _ in CORE_SKILL_DOCS]
        assert "finding-companies-and-contacts.md" in paths
        assert "enriching-and-researching.md" in paths
        assert "writing-outreach.md" in paths

    def test_provider_playbooks_included(self):
        paths = [path for path, _ in CORE_SKILL_DOCS]
        required_playbooks = [
            "provider-playbooks/apollo.md",
            "provider-playbooks/crustdata.md",
            "provider-playbooks/hunter.md",
            "provider-playbooks/dropleads.md",
            "provider-playbooks/leadmagic.md",
            "provider-playbooks/zerobounce.md",
            "provider-playbooks/hubspot.md",
            "provider-playbooks/salesforce.md",
            "provider-playbooks/attio.md",
            "provider-playbooks/instantly.md",
            "provider-playbooks/lemlist.md",
            "provider-playbooks/exa.md",
            "provider-playbooks/firecrawl.md",
            "provider-playbooks/apify.md",
        ]
        for pb in required_playbooks:
            assert pb in paths, f"Missing provider playbook: {pb}"

    def test_recipes_included(self):
        paths = [path for path, _ in CORE_SKILL_DOCS]
        assert "recipes/build-tam.md" in paths
        assert "recipes/linkedin-url-lookup.md" in paths
        assert "recipes/portfolio-prospecting.md" in paths

    def test_all_entries_have_description(self):
        for path, desc in CORE_SKILL_DOCS:
            assert desc, f"Missing description for {path}"
            assert len(desc) > 10, f"Description too short for {path}"

    def test_skill_md_first(self):
        """SKILL.md should be the first doc (highest priority)."""
        assert CORE_SKILL_DOCS[0][0] == "SKILL.md"

    def test_skills_base_url_correct(self):
        assert SKILLS_BASE.startswith("https://")
        assert "deepline.com" in SKILLS_BASE


# ---------------------------------------------------------------------------
# LOCAL_SKILL_DOCS content
# ---------------------------------------------------------------------------

class TestLocalSkillDocs:
    def test_recently_hired_documented(self):
        assert "recently_hired" in LOCAL_SKILL_DOCS

    def test_icypeas_mentioned_for_hire_date(self):
        assert "Icypeas" in LOCAL_SKILL_DOCS or "icypeas" in LOCAL_SKILL_DOCS

    def test_dropleads_limitation_mentioned(self):
        """Dropleads does NOT support recently_hired — docs should say so."""
        text = LOCAL_SKILL_DOCS.lower()
        assert "dropleads" in text

    def test_example_code_present(self):
        assert "search_prospects" in LOCAL_SKILL_DOCS


# ---------------------------------------------------------------------------
# load_skill_docs — async
# ---------------------------------------------------------------------------

class TestLoadSkillDocs:
    def test_successful_fetch_returns_content(self):
        """When all docs are fetched, result should contain their content."""
        async def _test():
            fake_content = "# Test skill\n\nSome content"
            with patch("deepline_gtm_agent.skills._fetch", return_value=fake_content):
                result = await load_skill_docs()
                assert fake_content in result
        asyncio.run(_test())

    def test_failed_fetch_returns_empty_for_doc(self):
        """Failed fetches should be skipped gracefully."""
        async def _test():
            async def fake_fetch(url):
                if "SKILL.md" in url:
                    return "# SKILL content"
                return ""  # all others fail
            with patch("deepline_gtm_agent.skills._fetch", side_effect=fake_fetch):
                result = await load_skill_docs()
                assert "SKILL content" in result
        asyncio.run(_test())

    def test_local_skill_docs_always_appended(self):
        """LOCAL_SKILL_DOCS should always be in the result."""
        async def _test():
            with patch("deepline_gtm_agent.skills._fetch", return_value=""):
                result = await load_skill_docs()
                assert "recently_hired" in result or "last30days" in result
        asyncio.run(_test())

    def test_all_docs_fetched_concurrently(self):
        """All docs should be fetched (concurrent asyncio.gather)."""
        fetched_urls = []
        async def _test():
            async def tracking_fetch(url):
                fetched_urls.append(url)
                return "content"
            with patch("deepline_gtm_agent.skills._fetch", side_effect=tracking_fetch):
                await load_skill_docs()
        asyncio.run(_test())
        assert len(fetched_urls) == len(CORE_SKILL_DOCS)

    def test_sections_separated_by_divider(self):
        async def _test():
            with patch("deepline_gtm_agent.skills._fetch", return_value="doc content"):
                result = await load_skill_docs()
                assert "---" in result
        asyncio.run(_test())


# ---------------------------------------------------------------------------
# load_skill_docs_sync
# ---------------------------------------------------------------------------

class TestLoadSkillDocsSync:
    def test_returns_string(self):
        with patch("deepline_gtm_agent.skills._fetch", return_value="content"):
            result = load_skill_docs_sync()
            assert isinstance(result, str)

    def test_graceful_on_runtime_error(self):
        """Should return empty string if called inside existing event loop."""
        with patch("asyncio.run", side_effect=RuntimeError("event loop already running")):
            result = load_skill_docs_sync()
            assert result == ""
