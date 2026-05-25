"""
Unit tests for deepline_gtm_agent.tools — core tool functions.

All external calls (deepline_execute, subprocess) are mocked.
"""

import csv
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Stub out deepagents and langchain imports so tests run without those deps
for mod in ["deepagents", "langchain_core", "langchain_core.tools"]:
    sys.modules.setdefault(mod, MagicMock())

from deepline_gtm_agent.tools import (
    _employee_ranges,
    _expand_title,
    _normalize_linkedin_url,
    _normalize_location,
    _work_dir,
    batch_enrich,
    enrich_person,
    find_linkedin,
    research_company,
    search_companies,
    search_prospects,
    verify_email,
    waterfall_enrich,
    web_research,
)


# ---------------------------------------------------------------------------
# _normalize_linkedin_url
# ---------------------------------------------------------------------------

class TestNormalizeLinkedInUrl:
    def test_already_https(self):
        url = "https://www.linkedin.com/in/reidhoffman"
        assert _normalize_linkedin_url(url) == url

    def test_http_to_https(self):
        assert _normalize_linkedin_url("http://www.linkedin.com/in/jane") == "https://www.linkedin.com/in/jane"

    def test_no_scheme(self):
        assert _normalize_linkedin_url("linkedin.com/in/jane") == "https://www.linkedin.com/in/jane"

    def test_www_no_scheme(self):
        assert _normalize_linkedin_url("www.linkedin.com/in/jane") == "https://www.linkedin.com/in/jane"

    def test_path_only(self):
        assert _normalize_linkedin_url("/in/jane") == "https://www.linkedin.com/in/jane"

    def test_path_no_slash(self):
        assert _normalize_linkedin_url("in/jane") == "https://www.linkedin.com/in/jane"

    def test_empty_string(self):
        assert _normalize_linkedin_url("") == ""

    def test_trailing_slash_removed(self):
        result = _normalize_linkedin_url("https://www.linkedin.com/in/jane/")
        assert result == "https://www.linkedin.com/in/jane"

    def test_sales_navigator_url_logs_warning(self):
        """Sales Navigator URLs should log a warning but still return."""
        url = "https://www.linkedin.com/sales/lead/ACoAA,NAME_SEARCH"
        with patch("deepline_gtm_agent.tools.logger") as mock_log:
            result = _normalize_linkedin_url(url)
            mock_log.warning.assert_called_once()
            assert "Sales Navigator" in mock_log.warning.call_args[0][0]
        assert result == url  # returns as-is (warning only)


# ---------------------------------------------------------------------------
# _work_dir
# ---------------------------------------------------------------------------

class TestWorkDir:
    def test_creates_under_home_deepline(self, tmp_path):
        with patch("deepline_gtm_agent.tools.Path.home", return_value=tmp_path):
            d = _work_dir("test-slug")
            assert d.exists()
            assert "deepline" in str(d)
            assert "test-slug" in str(d)

    def test_never_uses_tmp(self, tmp_path):
        with patch("deepline_gtm_agent.tools.Path.home", return_value=tmp_path):
            d = _work_dir("abc")
            assert "/tmp" not in str(d)

    def test_auto_slug_when_none(self, tmp_path):
        with patch("deepline_gtm_agent.tools.Path.home", return_value=tmp_path):
            d = _work_dir()
            assert d.exists()


# ---------------------------------------------------------------------------
# _expand_title
# ---------------------------------------------------------------------------

class TestExpandTitle:
    def test_gtm_engineer_expands(self):
        result = _expand_title("gtm engineer")
        assert len(result) > 1
        assert any("GTM" in t or "Growth" in t for t in result)

    def test_revops_expands(self):
        result = _expand_title("revops")
        assert any("Revenue Operations" in t or "RevOps" in t for t in result)

    def test_devrel_expands(self):
        result = _expand_title("devrel")
        assert any("Developer" in t for t in result)

    def test_unknown_title_returns_as_list(self):
        result = _expand_title("VP of Engineering")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_partial_match(self):
        result = _expand_title("ai engineer")
        assert len(result) > 1

    def test_case_insensitive(self):
        lower = _expand_title("GTM ENGINEER")
        upper = _expand_title("gtm engineer")
        # Both should expand (case normalized internally)
        assert len(lower) >= 1 and len(upper) >= 1


# ---------------------------------------------------------------------------
# _normalize_location
# ---------------------------------------------------------------------------

class TestNormalizeLocation:
    def test_nyc_maps_to_us(self):
        country, hint = _normalize_location("nyc")
        assert country == "United States"

    def test_london_maps_to_uk(self):
        country, hint = _normalize_location("london")
        assert country == "United Kingdom"

    def test_berlin_maps_to_germany(self):
        country, hint = _normalize_location("berlin")
        assert country == "Germany"

    def test_sf_maps_to_us(self):
        country, _ = _normalize_location("sf")
        assert country == "United States"

    def test_san_francisco_city_hint(self):
        country, hint = _normalize_location("san francisco")
        assert country == "United States"
        assert hint == "san francisco"

    def test_country_passthrough(self):
        country, hint = _normalize_location("Canada")
        assert country == "Canada"

    def test_case_insensitive(self):
        country, _ = _normalize_location("NEW YORK CITY")
        assert country == "United States"


# ---------------------------------------------------------------------------
# _employee_ranges
# ---------------------------------------------------------------------------

class TestEmployeeRanges:
    def test_small_company(self):
        result = _employee_ranges(1, 50)
        assert "1-10" in result
        assert "11-50" in result
        assert "51-200" not in result

    def test_mid_market(self):
        result = _employee_ranges(51, 500)
        assert "51-200" in result
        assert "201-500" in result
        assert "1-10" not in result

    def test_enterprise(self):
        result = _employee_ranges(1001, None)
        assert "1001-5000" in result
        assert "5001-10000" in result

    def test_none_min(self):
        result = _employee_ranges(None, 200)
        assert "1-10" in result
        assert "51-200" in result

    def test_none_both(self):
        result = _employee_ranges(None, None)
        assert len(result) > 0  # returns all ranges


# ---------------------------------------------------------------------------
# enrich_person — wiza first, dropleads second, then hunter
# ---------------------------------------------------------------------------

class TestEnrichPerson:
    def _mock_execute(self, responses: dict):
        """Build a side_effect fn that returns responses by tool_id."""
        def execute(tool_id, payload):
            if tool_id in responses:
                return responses[tool_id]
            return {}
        return execute

    def test_wiza_first_priority(self):
        """wiza should be called first and return immediately on hit."""
        with patch("deepline_gtm_agent.tools.deepline_execute") as mock_exec:
            mock_exec.return_value = {"email": "jane@acme.com", "provider": "wiza"}
            result = enrich_person(linkedin_url="https://www.linkedin.com/in/jane")
            first_call = mock_exec.call_args_list[0]
            assert first_call[0][0] == "wiza_enrich_person"
            assert result["provider"] == "wiza"

    def test_dropleads_second_on_wiza_miss(self):
        """When wiza misses, dropleads should be called next."""
        call_order = []
        def execute(tool_id, payload):
            call_order.append(tool_id)
            if tool_id == "dropleads_email_finder":
                return {"email": "jane@acme.com"}
            return {}  # wiza miss
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = enrich_person(
                linkedin_url="https://www.linkedin.com/in/jane",
                first_name="Jane",
                last_name="Doe",
                company_domain="acme.com",
            )
            assert call_order[0] == "wiza_enrich_person"
            assert "dropleads_email_finder" in call_order
            assert result["provider"] == "dropleads"

    def test_hunter_third_on_tier1_miss(self):
        """Hunter should be called after wiza and dropleads both miss."""
        call_order = []
        def execute(tool_id, payload):
            call_order.append(tool_id)
            if tool_id == "hunter_email_finder":
                return {"email": "jane@acme.com"}
            return {}
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = enrich_person(
                first_name="Jane", last_name="Doe", company_domain="acme.com",
                linkedin_url="https://www.linkedin.com/in/jane",
            )
            assert call_order.index("wiza_enrich_person") < call_order.index("dropleads_email_finder")
            assert call_order.index("dropleads_email_finder") < call_order.index("hunter_email_finder")

    def test_no_identifiers_returns_error(self):
        result = enrich_person()
        assert "error" in result

    def test_email_only_identifier_ok(self):
        with patch("deepline_gtm_agent.tools.deepline_execute", return_value={}):
            result = enrich_person(email="jane@acme.com")
            # Should attempt enrichment (not return early with error)
            assert "error" not in result or "Provide" not in result.get("error", "")

    def test_exception_in_wiza_falls_through(self):
        """Exception in wiza should not crash — falls to next provider."""
        call_order = []
        def execute(tool_id, payload):
            call_order.append(tool_id)
            if tool_id == "wiza_enrich_person":
                raise Exception("wiza timeout")
            if tool_id == "hunter_email_finder":
                return {"email": "jane@acme.com"}
            return {}
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = enrich_person(
                linkedin_url="https://www.linkedin.com/in/jane",
                first_name="Jane", last_name="Doe", company_domain="acme.com",
            )
            assert "wiza_enrich_person" in call_order
            assert result.get("email") or "error" in result  # either found or graceful miss


# ---------------------------------------------------------------------------
# waterfall_enrich — wiza first tier
# ---------------------------------------------------------------------------

class TestWaterfallEnrich:
    def test_wiza_is_first_provider(self):
        with patch("deepline_gtm_agent.tools.deepline_execute") as mock_exec:
            mock_exec.return_value = {"email": "jane@acme.com"}
            result = waterfall_enrich(linkedin_url="https://linkedin.com/in/jane")
            first_call = mock_exec.call_args_list[0]
            assert first_call[0][0] == "wiza_enrich_person"
            assert result["provider"] == "wiza_enrich_person"

    def test_waterfall_stops_on_first_hit(self):
        call_count = 0
        def execute(tool_id, payload):
            nonlocal call_count
            call_count += 1
            if tool_id == "wiza_enrich_person":
                return {"email": "jane@acme.com"}
            return {}
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = waterfall_enrich(linkedin_url="https://linkedin.com/in/jane")
            assert call_count == 1  # stopped at wiza
            assert result["email"] == "jane@acme.com"

    def test_exhausted_waterfall_returns_error(self):
        with patch("deepline_gtm_agent.tools.deepline_execute", return_value={}):
            result = waterfall_enrich(first_name="Ghost", last_name="Person")
            assert "error" in result
            assert "providers_tried" in result
            assert len(result["providers_tried"]) > 0

    def test_no_identifiers_returns_error(self):
        result = waterfall_enrich()
        assert "error" in result

    def test_dropleads_after_wiza_miss(self):
        call_order = []
        def execute(tool_id, payload):
            call_order.append(tool_id)
            if tool_id == "dropleads_email_finder":
                return {"email": "hit@acme.com"}
            return {}
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = waterfall_enrich(
                linkedin_url="https://linkedin.com/in/jane",
                first_name="Jane", last_name="Doe", company_domain="acme.com",
            )
            assert "wiza_enrich_person" in call_order
            assert call_order.index("wiza_enrich_person") < call_order.index("dropleads_email_finder")
            assert result["provider"] == "dropleads_email_finder"

    def test_provider_tried_list_populated(self):
        """providers_tried should list every provider attempted."""
        with patch("deepline_gtm_agent.tools.deepline_execute", return_value={}):
            result = waterfall_enrich(
                linkedin_url="https://linkedin.com/in/jane",
                first_name="Jane", last_name="Doe", company_domain="acme.com",
            )
            assert "providers_tried" in result
            assert "wiza_enrich_person" in result["providers_tried"]


# ---------------------------------------------------------------------------
# batch_enrich — subprocess-based deepline enrich
# ---------------------------------------------------------------------------

class TestBatchEnrich:
    def _write_test_csv(self, tmp_path, rows=None) -> Path:
        if rows is None:
            rows = [{"linkedin_url": "https://linkedin.com/in/jane", "name": "Jane Doe"}]
        p = tmp_path / "test_input.csv"
        with open(p, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return p

    def test_missing_input_returns_error(self):
        result = batch_enrich("/nonexistent/path.csv")
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_pilot_mode_default(self, tmp_path):
        """Default call uses --rows 0:1 (pilot)."""
        csv_path = self._write_test_csv(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "{}"
        mock_result.stderr = ""

        with patch("deepline_gtm_agent.tools.subprocess.run", return_value=mock_result) as mock_run, \
             patch("deepline_gtm_agent.tools._work_dir", return_value=tmp_path), \
             patch("deepline_gtm_agent.tools.Path.home", return_value=tmp_path):
            result = batch_enrich(str(csv_path))
            cmd = mock_run.call_args[0][0]
            assert "--rows" in cmd
            assert "0:1" in cmd
            assert result["pilot_done"] is True

    def test_full_run_skips_rows_flag(self, tmp_path):
        """full_run=True should not include --rows."""
        csv_path = self._write_test_csv(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="{}", stderr="")
        with patch("deepline_gtm_agent.tools.subprocess.run", return_value=mock_result) as mock_run, \
             patch("deepline_gtm_agent.tools._work_dir", return_value=tmp_path):
            batch_enrich(str(csv_path), full_run=True)
            cmd = mock_run.call_args[0][0]
            assert "--rows" not in cmd

    def test_output_written_to_work_dir(self, tmp_path):
        """Output CSV should be in ~/deepline/data/ not /tmp."""
        csv_path = self._write_test_csv(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="{}", stderr="")
        with patch("deepline_gtm_agent.tools.subprocess.run", return_value=mock_result), \
             patch("deepline_gtm_agent.tools._work_dir", return_value=tmp_path):
            result = batch_enrich(str(csv_path))
            assert "/tmp" not in result.get("output_csv", "")

    def test_cli_not_found_returns_error(self, tmp_path):
        csv_path = self._write_test_csv(tmp_path)
        with patch("deepline_gtm_agent.tools.subprocess.run",
                   side_effect=FileNotFoundError("deepline not found")), \
             patch("deepline_gtm_agent.tools._work_dir", return_value=tmp_path):
            result = batch_enrich(str(csv_path))
            assert "error" in result
            assert "deepline CLI not found" in result["error"]

    def test_timeout_returns_error(self, tmp_path):
        csv_path = self._write_test_csv(tmp_path)
        with patch("deepline_gtm_agent.tools.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="deepline", timeout=300)), \
             patch("deepline_gtm_agent.tools._work_dir", return_value=tmp_path):
            result = batch_enrich(str(csv_path))
            assert "error" in result
            assert "timed out" in result["error"].lower()

    def test_nonzero_exit_returns_error(self, tmp_path):
        csv_path = self._write_test_csv(tmp_path)
        mock_result = MagicMock(returncode=1, stdout="", stderr="provider auth failed")
        with patch("deepline_gtm_agent.tools.subprocess.run", return_value=mock_result), \
             patch("deepline_gtm_agent.tools._work_dir", return_value=tmp_path):
            result = batch_enrich(str(csv_path))
            assert "error" in result

    def test_custom_columns_passed(self, tmp_path):
        csv_path = self._write_test_csv(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="{}", stderr="")
        cols = [{"tool_id": "wiza_enrich_person"}, {"tool_id": "hunter_email_finder"}]
        with patch("deepline_gtm_agent.tools.subprocess.run", return_value=mock_result) as mock_run, \
             patch("deepline_gtm_agent.tools._work_dir", return_value=tmp_path):
            batch_enrich(str(csv_path), columns=cols)
            cmd = mock_run.call_args[0][0]
            # Both --with args should appear
            assert cmd.count("--with") == 2

    def test_default_columns_include_wiza_first(self, tmp_path):
        """Default email waterfall must have wiza as first column."""
        csv_path = self._write_test_csv(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="{}", stderr="")
        with patch("deepline_gtm_agent.tools.subprocess.run", return_value=mock_result) as mock_run, \
             patch("deepline_gtm_agent.tools._work_dir", return_value=tmp_path):
            batch_enrich(str(csv_path))
            cmd = mock_run.call_args[0][0]
            # Find position of wiza and dropleads in --with args
            with_indices = [i for i, x in enumerate(cmd) if x == "--with"]
            assert len(with_indices) >= 2
            first_col = json.loads(cmd[with_indices[0] + 1])
            assert first_col["tool_id"] == "wiza_enrich_person"

    def test_next_step_message_in_pilot(self, tmp_path):
        csv_path = self._write_test_csv(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="{}", stderr="")
        with patch("deepline_gtm_agent.tools.subprocess.run", return_value=mock_result), \
             patch("deepline_gtm_agent.tools._work_dir", return_value=tmp_path):
            result = batch_enrich(str(csv_path))
            assert result.get("next_step") is not None
            assert "full_run=True" in result["next_step"]

    def test_next_step_none_on_full_run(self, tmp_path):
        csv_path = self._write_test_csv(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="{}", stderr="")
        with patch("deepline_gtm_agent.tools.subprocess.run", return_value=mock_result), \
             patch("deepline_gtm_agent.tools._work_dir", return_value=tmp_path):
            result = batch_enrich(str(csv_path), full_run=True)
            assert result.get("next_step") is None


# ---------------------------------------------------------------------------
# search_prospects
# ---------------------------------------------------------------------------

class TestSearchProspects:
    def test_recently_hired_routes_to_icypeas(self):
        """recently_hired_months should use icypeas_find_people."""
        call_order = []
        def execute(tool_id, payload):
            call_order.append(tool_id)
            if tool_id == "icypeas_find_people":
                return {"data": {"people": [{"fullName": "Jane Doe", "linkedinUrl": "https://li.com/in/jane"}]}}
            return {}
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = search_prospects(job_title="VP Sales", recently_hired_months=1)
            assert "icypeas" in result.get("provider", "")
            assert "icypeas_find_people" in call_order

    def test_dropleads_is_primary_provider(self):
        """Default search (no recently_hired) should use dropleads first."""
        call_order = []
        def execute(tool_id, payload):
            call_order.append(tool_id)
            if tool_id == "dropleads_search_people":
                return {"data": {"leads": [{"fullName": "John Smith"}], "total": 1}}
            return {}
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = search_prospects(job_title="VP Sales")
            assert call_order[0] == "dropleads_search_people"
            assert result["provider"] == "dropleads"

    def test_industry_filter_dropped_on_zero_results(self):
        """When industry filter returns 0 results, should retry without industry."""
        call_count = 0
        def execute(tool_id, payload):
            nonlocal call_count
            call_count += 1
            if tool_id == "dropleads_search_people":
                filters = payload.get("filters", {})
                if "industries" in filters:
                    return {"data": {"leads": [], "total": 0}}
                return {"data": {"leads": [{"fullName": "Jane"}], "total": 1}}
            return {}
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = search_prospects(job_title="VP", company_industry="SaaS")
            assert "dropleads" in result.get("provider", "")
            assert result.get("note") and "industry" in result["note"].lower()

    def test_city_location_note_added(self):
        """City-level location should produce a note about country-only search."""
        def execute(tool_id, payload):
            if tool_id == "dropleads_search_people":
                return {"data": {"leads": [{"fullName": "Jane"}], "total": 1}}
            return {}
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = search_prospects(job_title="VP", person_location="san francisco")
            assert result.get("note") and "san francisco" in result["note"].lower()

    def test_icypeas_fallback_when_dropleads_empty(self):
        """Icypeas should be tried as fallback when dropleads returns nothing."""
        def execute(tool_id, payload):
            if tool_id == "dropleads_search_people":
                return {"data": {"leads": [], "total": 0}}
            if tool_id == "icypeas_find_people":
                return {"data": {"people": [{"fullName": "Jane Doe"}]}}
            return {}
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = search_prospects(job_title="LLM Engineer")
            assert "icypeas" in result.get("provider", "")

    def test_no_results_returns_error_with_tip(self):
        with patch("deepline_gtm_agent.tools.deepline_execute", return_value={}):
            result = search_prospects(job_title="VP Sales")
            assert "error" in result
            assert "tip" in result

    def test_prospects_have_has_email_field(self):
        def execute(tool_id, payload):
            if tool_id == "dropleads_search_people":
                return {"data": {"leads": [
                    {"fullName": "Jane", "email": "jane@a.com"},
                    {"fullName": "John"},
                ], "total": 2}}
            return {}
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = search_prospects(job_title="VP")
            prospects = result.get("prospects", [])
            assert prospects[0]["has_email"] is True
            assert prospects[1]["has_email"] is False


# ---------------------------------------------------------------------------
# research_company
# ---------------------------------------------------------------------------

class TestResearchCompany:
    def test_no_identifiers_returns_error(self):
        result = research_company()
        assert "error" in result

    def test_crustdata_primary_for_domain(self):
        with patch("deepline_gtm_agent.tools.deepline_execute") as mock_exec:
            mock_exec.return_value = {"company": "Acme Corp", "headcount": 200}
            result = research_company(domain="acme.com")
            first_call = mock_exec.call_args_list[0]
            assert first_call[0][0] == "crustdata_company_enrichment"
            assert result["provider"] == "crustdata"

    def test_exa_fallback_when_crustdata_empty(self):
        call_order = []
        def execute(tool_id, payload):
            call_order.append(tool_id)
            if tool_id == "crustdata_company_enrichment":
                return {}  # miss
            if tool_id == "exa_research":
                return {"data": {"output": "Acme Corp is a SaaS company..."}}
            return {}
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = research_company(domain="acme.com")
            assert "exa" in result.get("provider", "")

    def test_company_name_routes_to_exa(self):
        """company_name only (no domain) should route to Exa."""
        with patch("deepline_gtm_agent.tools.deepline_execute") as mock_exec:
            mock_exec.return_value = {"data": {"output": "Acme description"}}
            result = research_company(company_name="Acme Corp")
            assert mock_exec.called


# ---------------------------------------------------------------------------
# web_research
# ---------------------------------------------------------------------------

class TestWebResearch:
    def test_calls_exa_research(self):
        with patch("deepline_gtm_agent.tools.deepline_execute") as mock_exec:
            mock_exec.return_value = {"data": {"output": "Some research"}}
            result = web_research("what is Acme Corp")
            assert mock_exec.call_args[0][0] == "exa_research"
            assert result["provider"] == "exa_research"

    def test_query_preserved_in_result(self):
        with patch("deepline_gtm_agent.tools.deepline_execute",
                   return_value={"data": {"output": "..."}}):
            result = web_research("funding round for Acme")
            assert result["query"] == "funding round for Acme"

    def test_exception_returns_error_dict(self):
        with patch("deepline_gtm_agent.tools.deepline_execute",
                   side_effect=Exception("network error")):
            result = web_research("test query")
            assert "error" in result


# ---------------------------------------------------------------------------
# verify_email
# ---------------------------------------------------------------------------

class TestVerifyEmail:
    def test_leadmagic_primary(self):
        with patch("deepline_gtm_agent.tools.deepline_execute") as mock_exec:
            mock_exec.return_value = {"email_status": "valid"}
            result = verify_email("jane@acme.com")
            first_call = mock_exec.call_args_list[0]
            assert first_call[0][0] == "leadmagic_email_validation"
            assert result["valid"] is True
            assert result["safe_to_send"] is True

    def test_leadmagic_invalid(self):
        with patch("deepline_gtm_agent.tools.deepline_execute",
                   return_value={"email_status": "invalid"}):
            result = verify_email("bad@nonexistent.com")
            assert result["valid"] is False
            assert result["safe_to_send"] is False

    def test_zerobounce_fallback_when_leadmagic_unknown(self):
        call_order = []
        def execute(tool_id, payload):
            call_order.append(tool_id)
            if tool_id == "leadmagic_email_validation":
                return {"email_status": "unknown"}
            if tool_id == "zerobounce_batch_validate":
                return {"email_batch": [{"status": "valid", "sub_status": ""}]}
            return {}
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = verify_email("jane@acme.com")
            assert "zerobounce" in result["provider"]
            assert result["valid"] is True

    def test_catch_all_not_safe_to_send(self):
        def execute(tool_id, payload):
            if tool_id == "leadmagic_email_validation":
                return {"email_status": "unknown"}
            return {"email_batch": [{"status": "valid", "sub_status": "role_based"}]}
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = verify_email("info@acme.com")
            assert result["safe_to_send"] is False

    def test_zerobounce_disposable_not_safe(self):
        def execute(tool_id, payload):
            if tool_id == "leadmagic_email_validation":
                return {"email_status": "unknown"}
            return {"email_batch": [{"status": "valid", "sub_status": "disposable"}]}
        with patch("deepline_gtm_agent.tools.deepline_execute", side_effect=execute):
            result = verify_email("temp@mailinator.com")
            assert result["safe_to_send"] is False

    def test_email_passed_through(self):
        with patch("deepline_gtm_agent.tools.deepline_execute",
                   return_value={"email_status": "valid"}):
            result = verify_email("jane@acme.com")
            assert result["email"] == "jane@acme.com"


# ---------------------------------------------------------------------------
# find_linkedin
# ---------------------------------------------------------------------------

class TestFindLinkedin:
    def test_deepline_native_primary_when_domain_given(self):
        with patch("deepline_gtm_agent.tools.deepline_execute") as mock_exec:
            mock_exec.return_value = {"linkedin_url": "https://linkedin.com/in/jane"}
            result = find_linkedin("Jane", "Doe", company_domain="acme.com")
            first_call = mock_exec.call_args_list[0]
            assert first_call[0][0] == "deepline_native_enrich_contact"
            assert result["linkedin_url"] == "https://linkedin.com/in/jane"
            assert result["confidence"] == "high"

    def test_exa_fallback_when_no_domain(self):
        with patch("deepline_gtm_agent.tools.deepline_execute") as mock_exec:
            mock_exec.return_value = {"data": {"output": "https://linkedin.com/in/jane-doe"}}
            result = find_linkedin("Jane", "Doe")
            assert mock_exec.called
            assert "linkedin.com/in/" in result.get("linkedin_url", "")
            assert result["confidence"] == "medium"

    def test_empty_result_on_no_match(self):
        with patch("deepline_gtm_agent.tools.deepline_execute", return_value={}):
            result = find_linkedin("Ghost", "Person", company_domain="unknown.com")
            assert result.get("linkedin_url") == ""
            assert result["confidence"] == "none"


# ---------------------------------------------------------------------------
# search_companies
# ---------------------------------------------------------------------------

class TestSearchCompanies:
    def test_calls_exa_with_criteria(self):
        with patch("deepline_gtm_agent.tools.deepline_execute") as mock_exec:
            mock_exec.return_value = {"data": {"output": "List of SaaS companies..."}}
            result = search_companies(industry="SaaS", headcount_min=50, headcount_max=500)
            assert mock_exec.called
            call_args = mock_exec.call_args[0]
            assert call_args[0] == "exa_research"
            # Criteria should be in the instructions
            instructions = call_args[1]["instructions"]
            assert "SaaS" in instructions
            assert "50" in instructions or "500" in instructions

    def test_no_criteria_uses_general(self):
        with patch("deepline_gtm_agent.tools.deepline_execute",
                   return_value={"data": {"output": "..."}}):
            result = search_companies()
            assert result["provider"] == "exa_research"

    def test_exa_failure_returns_error(self):
        with patch("deepline_gtm_agent.tools.deepline_execute",
                   side_effect=Exception("exa down")):
            result = search_companies(industry="SaaS")
            assert "error" in result
