"""Tests for build_org_chart tool function in tools.py."""

import os
import sys
import types
import importlib
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: load tools.py without triggering heavy __init__.py imports
# ---------------------------------------------------------------------------

_pkg_dir = os.path.join(os.path.dirname(__file__), os.pardir, "deepline_gtm_agent")

# Load orgchart module and register in sys.modules
_oc_spec = importlib.util.spec_from_file_location(
    "deepline_gtm_agent.orgchart",
    os.path.join(_pkg_dir, "orgchart.py"),
)
_oc_mod = importlib.util.module_from_spec(_oc_spec)
_oc_spec.loader.exec_module(_oc_mod)
sys.modules["deepline_gtm_agent.orgchart"] = _oc_mod

# Create a stub deepline module with a mock deepline_execute
_deepline_stub = types.ModuleType("deepline_gtm_agent.deepline")
_deepline_stub.deepline_execute = MagicMock(return_value={})
sys.modules["deepline_gtm_agent.deepline"] = _deepline_stub

# Ensure parent package exists in sys.modules
if "deepline_gtm_agent" not in sys.modules:
    _pkg_stub = types.ModuleType("deepline_gtm_agent")
    _pkg_stub.__path__ = [_pkg_dir]
    sys.modules["deepline_gtm_agent"] = _pkg_stub

# Now load tools.py
_tools_spec = importlib.util.spec_from_file_location(
    "deepline_gtm_agent.tools",
    os.path.join(_pkg_dir, "tools.py"),
)
_tools_mod = importlib.util.module_from_spec(_tools_spec)
_tools_spec.loader.exec_module(_tools_mod)
sys.modules["deepline_gtm_agent.tools"] = _tools_mod

build_org_chart = _tools_mod.build_org_chart
# Reference to the mock so we can swap side_effect per test
_mock_execute = _deepline_stub.deepline_execute

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_APOLLO_TIER1 = {
    "people": [
        {
            "name": "Charles Huang",
            "title": "VP Engineering",
            "linkedin_url": "https://linkedin.com/in/charles",
            "city": "San Francisco",
            "state": "California",
            "country": "United States",
            "seniority": "vp",
            "departments": ["engineering"],
            "email": "charles@example.com",
        },
    ]
}

MOCK_APOLLO_TIER2 = {
    "people": [
        {
            "name": "Ron P",
            "title": "Senior Director of Engineering",
            "linkedin_url": "",
            "city": "San Francisco",
            "state": "California",
            "country": "United States",
            "seniority": "director",
            "departments": ["engineering"],
            "email": "",
        },
        {
            "name": "Manpreet Singh",
            "title": "Head of Engineering, Identity",
            "linkedin_url": "https://linkedin.com/in/manpreet",
            "city": "San Francisco",
            "state": "California",
            "country": "United States",
            "seniority": "director",
            "departments": ["engineering"],
            "email": "",
        },
    ]
}

MOCK_APOLLO_TIER3 = {
    "people": [
        {
            "name": "Amy Seaman",
            "title": "Engineering Manager",
            "linkedin_url": "",
            "city": "Seattle",
            "state": "Washington",
            "country": "United States",
            "seniority": "manager",
            "departments": ["engineering"],
            "email": "",
        },
    ]
}

MOCK_APOLLO_TIER4 = {"people": []}

MOCK_DROPLEADS = {
    "success": True,
    "pagination": {"page": 1, "limit": 100, "total": 2, "totalPages": 1},
    "leads": [
        {
            "fullName": "Charles Huang",
            "title": "VP Engineering",
            "linkedinUrl": "https://linkedin.com/in/charles",
            "location": "San Francisco, CA",
            "email": "charles@example.com",
        },
        {
            "fullName": "Jake Torres",
            "title": "Senior Software Engineer",
            "linkedinUrl": "https://linkedin.com/in/jake-torres",
            "location": "Austin, TX",
            "email": "",
        },
    ],
}

MOCK_DEEPLINE_NATIVE = {
    "status": "SUCCEEDED",
    "output": {
        "persons": [
            {
                "full_name": "Lisa Chen",
                "first_name": "Lisa",
                "last_name": "Chen",
                "title": "Director of Marketing",
                "linkedin_url": "https://linkedin.com/in/lisa-chen",
                "professional_email": "lisa@acme.com",
                "seniority": "Director",
                "department": "Marketing",
                "country": "United States",
            },
        ]
    }
}

MOCK_DEEPLINE_NATIVE_EMPTY = {"status": "SUCCEEDED", "output": {"persons": []}}

MOCK_JOB_LISTINGS = {
    "listings": [
        {"title": "Senior Engineer, Platform", "category": "Engineering"},
        {"title": "Product Manager, Identity", "category": "Product"},
    ]
}

MOCK_EXA_SEARCH = {
    "results": [{"url": "https://www.acme.com/about"}]
}


def _mock_execute_basic(tool_id, payload):
    """Mock deepline_execute for basic org chart test."""
    if tool_id == "apollo_search_people":
        seniority = payload.get("person_seniorities", [])
        if "owner" in seniority or "c_suite" in seniority:
            return MOCK_APOLLO_TIER1
        if "head" in seniority or "director" in seniority:
            return MOCK_APOLLO_TIER2
        if "manager" in seniority:
            return MOCK_APOLLO_TIER3
        return MOCK_APOLLO_TIER4
    if tool_id == "dropleads_search_people":
        return MOCK_DROPLEADS
    if tool_id == "deepline_native_search_contact":
        title_filters = payload.get("title_filters", [])
        if title_filters and "Director" in title_filters[0].get("filter", ""):
            return MOCK_DEEPLINE_NATIVE
        return MOCK_DEEPLINE_NATIVE_EMPTY
    if tool_id == "crustdata_job_listings":
        return MOCK_JOB_LISTINGS
    return {}


def _mock_execute_name_only(tool_id, payload):
    """Mock deepline_execute for name-only test (no LinkedIn)."""
    if tool_id == "exa_search":
        return MOCK_EXA_SEARCH
    return _mock_execute_basic(tool_id, payload)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildOrgChartBasic:
    def test_returns_people_hierarchy_summary(self):
        _mock_execute.reset_mock()
        _mock_execute.side_effect = _mock_execute_basic

        result = build_org_chart(
            first_name="Amy",
            last_name="Seaman",
            company_domain="acme.com",
            company_name="Acme Corp",
        )

        assert "error" not in result
        assert "people" in result
        assert "hierarchy" in result
        assert "summary" in result

        # Should have people from Apollo + Dropleads (deduplicated)
        # Only people connected in the hierarchy are included (management chain + peers + reports)
        people = result["people"]
        assert len(people) >= 3  # Charles (VP) -> Ron (Sr Dir) -> Amy (Manager) chain

        # Hierarchy should have edges
        hierarchy = result["hierarchy"]
        assert "edges" in hierarchy
        assert "root" in hierarchy
        assert "target" in hierarchy

        # Summary should have target info
        summary = result["summary"]
        assert summary["target"] == "Amy Seaman"
        assert summary["domain"] == "acme.com"
        assert summary["total_people"] >= 3

    def test_manager_detected(self):
        _mock_execute.reset_mock()
        _mock_execute.side_effect = _mock_execute_basic

        result = build_org_chart(
            first_name="Amy",
            last_name="Seaman",
            company_domain="acme.com",
            company_name="Acme Corp",
        )

        summary = result["summary"]
        # Amy is a manager; her manager should be someone more senior
        assert summary["manager"] is not None


class TestBuildOrgChartNameOnly:
    def test_resolves_domain_via_exa(self):
        _mock_execute.reset_mock()
        _mock_execute.side_effect = _mock_execute_name_only

        result = build_org_chart(
            first_name="Amy",
            last_name="Seaman",
            company_name="Acme Corp",
        )

        # Should still work - resolves domain via exa_search
        assert "people" in result
        assert "hierarchy" in result
        assert "summary" in result


class TestBuildOrgChartDedup:
    def test_deduplicates_across_sources(self):
        _mock_execute.reset_mock()
        _mock_execute.side_effect = _mock_execute_basic

        result = build_org_chart(
            first_name="Amy",
            last_name="Seaman",
            company_domain="acme.com",
            company_name="Acme Corp",
        )

        people = result["people"]
        # Charles Huang appears in both Apollo Tier 1 and Dropleads
        charles_entries = [v for v in people.values() if "charles" in v["name"].lower()]
        assert len(charles_entries) == 1, "Charles Huang should be deduplicated to one entry"
        assert len(charles_entries[0]["sources"]) >= 2, "Charles should have 2+ sources"
        assert charles_entries[0]["confidence"] in ("medium", "high")


class TestBuildOrgChartTargetIncluded:
    def test_target_always_in_people(self):
        _mock_execute.reset_mock()
        _mock_execute.side_effect = _mock_execute_basic

        result = build_org_chart(
            first_name="Amy",
            last_name="Seaman",
            company_domain="acme.com",
            company_name="Acme Corp",
        )

        people = result["people"]
        amy_entries = [v for v in people.values() if "amy" in v["name"].lower()]
        assert len(amy_entries) >= 1, "Target Amy Seaman should be in the people dict"


class TestBuildOrgChartNoInput:
    def test_returns_error(self):
        result = build_org_chart()
        assert "error" in result
