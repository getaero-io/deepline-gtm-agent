"""Tests for Waterfall.io integration - client and tool functions."""

import importlib
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Import modules directly (bypassing __init__.py to avoid deepagents dep)
# ---------------------------------------------------------------------------

_pkg_dir = os.path.join(os.path.dirname(__file__), os.pardir, "deepline_gtm_agent")

# Import waterfall_client
_spec_client = importlib.util.spec_from_file_location(
    "deepline_gtm_agent.waterfall_client",
    os.path.join(_pkg_dir, "waterfall_client.py"),
)
waterfall_client = importlib.util.module_from_spec(_spec_client)
sys.modules["deepline_gtm_agent.waterfall_client"] = waterfall_client
_spec_client.loader.exec_module(waterfall_client)

# Mock heavy deps so tools.py can be imported
sys.modules.setdefault("deepline_gtm_agent.deepline", MagicMock())
_mock_orgchart = MagicMock()
_mock_orgchart.slugify = MagicMock(return_value="test")
_mock_orgchart.classify_seniority = MagicMock(return_value="ic")
_mock_orgchart.SENIORITY_LABELS = {}
_mock_orgchart.extract_team_from_title = MagicMock(return_value="")
_mock_orgchart.extract_teams_from_jobs = MagicMock(return_value=set())
_mock_orgchart.assign_team = MagicMock(return_value="")
_mock_orgchart.build_hierarchy = MagicMock(return_value={})
sys.modules.setdefault("deepline_gtm_agent.orgchart", _mock_orgchart)

_spec_tools = importlib.util.spec_from_file_location(
    "deepline_gtm_agent.tools",
    os.path.join(_pkg_dir, "tools.py"),
)
tools_mod = importlib.util.module_from_spec(_spec_tools)
sys.modules["deepline_gtm_agent.tools"] = tools_mod
_spec_tools.loader.exec_module(tools_mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code=200, json_data=None, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = str(json_data)
    resp.headers = headers or {}
    return resp


# ---------------------------------------------------------------------------
# waterfall_client tests
# ---------------------------------------------------------------------------

class TestWaterfallRequest:
    @patch.dict(os.environ, {"WATERFALL_API_KEY": "test-key-123"})
    @patch("httpx.Client")
    def test_post_request(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = _mock_response(200, {"job_id": "abc-123"})

        result = waterfall_client.waterfall_request("POST", "/v1/prospector", payload={"domain": "stripe.com"})
        assert result == {"job_id": "abc-123"}
        mock_client.post.assert_called_once()

    @patch.dict(os.environ, {"WATERFALL_API_KEY": "test-key-123"})
    @patch("httpx.Client")
    def test_get_request(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = _mock_response(200, {"status": "SUCCEEDED", "output": {}})

        result = waterfall_client.waterfall_request("GET", "/v1/prospector", params={"job_id": "abc"})
        assert result["status"] == "SUCCEEDED"

    @patch.dict(os.environ, {"WATERFALL_API_KEY": ""})
    def test_missing_api_key(self):
        with pytest.raises(RuntimeError, match="WATERFALL_API_KEY not set"):
            waterfall_client.waterfall_request("GET", "/v1/prospector")

    @patch.dict(os.environ, {"WATERFALL_API_KEY": "test-key-123"})
    @patch("httpx.Client")
    def test_rate_limit_429(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = _mock_response(429, {}, headers={"Retry-After": "30"})

        with pytest.raises(RuntimeError, match="rate limited"):
            waterfall_client.waterfall_request("POST", "/v1/prospector", payload={})

    @patch.dict(os.environ, {"WATERFALL_API_KEY": "test-key-123"})
    @patch("httpx.Client")
    def test_unauthorized_401(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = _mock_response(401, {})

        with pytest.raises(RuntimeError, match="API key missing"):
            waterfall_client.waterfall_request("POST", "/v1/prospector", payload={})


class TestWaterfallAsyncJob:
    def test_polls_until_succeeded(self):
        with patch.dict(os.environ, {"WATERFALL_API_KEY": "test-key-123"}):
            with patch.object(waterfall_client, "waterfall_request") as mock_req:
                with patch.object(waterfall_client.time, "sleep"):
                    mock_req.side_effect = [
                        {"job_id": "job-1"},
                        {"status": "RUNNING"},
                        {"status": "SUCCEEDED", "output": {"persons": [{"first_name": "Jane"}]}},
                    ]
                    result = waterfall_client.waterfall_async_job("/v1/prospector", {"domain": "test.com"})
                    assert result["status"] == "SUCCEEDED"
                    assert result["output"]["persons"][0]["first_name"] == "Jane"
                    assert mock_req.call_count == 3

    def test_sync_endpoint_no_job_id(self):
        with patch.dict(os.environ, {"WATERFALL_API_KEY": "test-key-123"}):
            with patch.object(waterfall_client, "waterfall_request") as mock_req:
                mock_req.return_value = {"status": "SUCCEEDED", "output": {"persons": []}}
                result = waterfall_client.waterfall_async_job("/v1/search/contact", {"domain": "test.com"})
                assert result["status"] == "SUCCEEDED"
                assert mock_req.call_count == 1

    def test_job_failed(self):
        with patch.dict(os.environ, {"WATERFALL_API_KEY": "test-key-123"}):
            with patch.object(waterfall_client, "waterfall_request") as mock_req:
                with patch.object(waterfall_client.time, "sleep"):
                    mock_req.side_effect = [
                        {"job_id": "job-fail"},
                        {"status": "FAILED", "output": {}},
                    ]
                    result = waterfall_client.waterfall_async_job("/v1/prospector", {"domain": "test.com"})
                    assert result["status"] == "FAILED"


# ---------------------------------------------------------------------------
# Tool function tests (patch waterfall_client functions directly)
# ---------------------------------------------------------------------------

class TestWaterfallProspect:
    def test_basic_prospect(self):
        with patch.object(waterfall_client, "waterfall_async_job") as mock_job:
            mock_job.return_value = {
                "status": "SUCCEEDED",
                "output": {
                    "company": {"domain": "stripe.com", "company_name": "Stripe"},
                    "persons": [
                        {"first_name": "Jane", "last_name": "Doe", "title": "VP Sales"},
                        {"first_name": "John", "last_name": "Smith", "title": "Director Eng"},
                    ],
                },
            }
            result = tools_mod.waterfall_prospect(domain="stripe.com", title_filter="VP Sales OR Director")
            assert result["provider"] == "waterfall"
            assert result["status"] == "SUCCEEDED"
            assert result["count"] == 2
            assert result["persons"][0]["first_name"] == "Jane"
            call_payload = mock_job.call_args[0][1]
            assert call_payload["domain"] == "stripe.com"
            assert call_payload["verified_only"] is True

    def test_prospect_with_countries(self):
        with patch.object(waterfall_client, "waterfall_async_job") as mock_job:
            mock_job.return_value = {"status": "SUCCEEDED", "output": {"persons": []}}
            tools_mod.waterfall_prospect(domain="stripe.com", location_countries=["US", "GB"])
            call_payload = mock_job.call_args[0][1]
            assert call_payload["location_countries"] == ["US", "GB"]


class TestWaterfallEnrichContact:
    def test_enrich_by_linkedin(self):
        with patch.object(waterfall_client, "waterfall_async_job") as mock_job:
            mock_job.return_value = {
                "status": "SUCCEEDED",
                "output": {"person": {"first_name": "Jane", "professional_email": "jane@stripe.com"}},
            }
            result = tools_mod.waterfall_enrich_contact(linkedin="https://linkedin.com/in/janedoe")
            assert result["provider"] == "waterfall"
            assert result["first_name"] == "Jane"

    def test_enrich_by_name_domain(self):
        with patch.object(waterfall_client, "waterfall_async_job") as mock_job:
            mock_job.return_value = {
                "status": "SUCCEEDED",
                "output": {"person": {"first_name": "Jane", "last_name": "Doe"}},
            }
            result = tools_mod.waterfall_enrich_contact(first_name="Jane", last_name="Doe", domain="stripe.com")
            call_payload = mock_job.call_args[0][1]
            assert call_payload["first_name"] == "Jane"
            assert call_payload["domain"] == "stripe.com"

    def test_enrich_missing_identity(self):
        result = tools_mod.waterfall_enrich_contact()
        assert "error" in result


class TestWaterfallEnrichPhone:
    def test_phone_by_email(self):
        with patch.object(waterfall_client, "waterfall_async_job") as mock_job:
            mock_job.return_value = {
                "status": "SUCCEEDED",
                "output": {"person": {"mobile_phone": "+15551234567", "phone_numbers": ["+15551234567"]}},
            }
            result = tools_mod.waterfall_enrich_phone(email="jane@stripe.com")
            assert result["provider"] == "waterfall_phone"
            assert result["mobile_phone"] == "+15551234567"

    def test_phone_missing_identity(self):
        result = tools_mod.waterfall_enrich_phone()
        assert "error" in result


class TestWaterfallEnrichCompany:
    def test_enrich_by_domain(self):
        with patch.object(waterfall_client, "waterfall_async_job") as mock_job:
            mock_job.return_value = {
                "status": "SUCCEEDED",
                "output": {"company": {"domain": "stripe.com", "company_name": "Stripe", "size": "1001-5000"}},
            }
            result = tools_mod.waterfall_enrich_company(domain="stripe.com")
            assert result["provider"] == "waterfall_company"
            assert result["company_name"] == "Stripe"

    def test_enrich_company_missing_identity(self):
        result = tools_mod.waterfall_enrich_company()
        assert "error" in result


class TestWaterfallSearchContacts:
    def test_search_by_domain(self):
        with patch.object(waterfall_client, "waterfall_request") as mock_req:
            mock_req.return_value = {
                "status": "SUCCEEDED",
                "output": {"persons": [{"first_name": "Jane", "title": "VP Sales"}]},
            }
            result = tools_mod.waterfall_search_contacts(domain="stripe.com", seniorities=["vp"])
            assert result["provider"] == "waterfall_search"
            assert result["count"] == 1


class TestWaterfallSearchCompanies:
    def test_search_by_industry(self):
        with patch.object(waterfall_client, "waterfall_request") as mock_req:
            mock_req.return_value = {
                "status": "SUCCEEDED",
                "output": {"companies": [{"domain": "stripe.com", "company_name": "Stripe"}]},
            }
            result = tools_mod.waterfall_search_companies(industries=["fintech"], location_countries=["US"])
            assert result["provider"] == "waterfall_search"
            assert result["count"] == 1

    def test_search_no_filters(self):
        result = tools_mod.waterfall_search_companies()
        assert "error" in result


class TestWaterfallJobChange:
    def test_job_change_detected(self):
        with patch.object(waterfall_client, "waterfall_async_job") as mock_job:
            mock_job.return_value = {
                "status": "SUCCEEDED",
                "output": {
                    "job_change_status": "moved",
                    "person": {"first_name": "Jane", "company_name": "NewCo"},
                },
            }
            result = tools_mod.waterfall_job_change(
                company_domain="stripe.com",
                contact_linkedin="https://linkedin.com/in/janedoe",
            )
            assert result["provider"] == "waterfall_job_change"
            assert result["job_change_status"] == "moved"
            assert result["person"]["company_name"] == "NewCo"

    def test_no_change(self):
        with patch.object(waterfall_client, "waterfall_async_job") as mock_job:
            mock_job.return_value = {
                "status": "SUCCEEDED",
                "output": {"job_change_status": "no_change", "person": {}},
            }
            result = tools_mod.waterfall_job_change(company_domain="stripe.com", professional_email="jane@stripe.com")
            assert result["job_change_status"] == "no_change"

    def test_job_change_no_input(self):
        result = tools_mod.waterfall_job_change()
        assert "error" in result


class TestWaterfallVerifyEmail:
    def test_valid_email(self):
        with patch.object(waterfall_client, "waterfall_request") as mock_req:
            mock_req.return_value = {
                "output": {
                    "email": {
                        "email": "jane@stripe.com",
                        "email_status": "valid",
                        "smtp_provider": "google",
                        "mx_records": ["aspmx.l.google.com"],
                    },
                },
            }
            result = tools_mod.waterfall_verify_email(email="jane@stripe.com")
            assert result["provider"] == "waterfall_verify"
            assert result["email_status"] == "valid"
            assert result["valid"] is True
            assert result["safe_to_send"] is True
            assert result["smtp_provider"] == "google"

    def test_invalid_email(self):
        with patch.object(waterfall_client, "waterfall_request") as mock_req:
            mock_req.return_value = {
                "output": {
                    "email": {
                        "email": "fake@nope.com",
                        "email_status": "invalid",
                        "smtp_provider": "",
                        "mx_records": [],
                    },
                },
            }
            result = tools_mod.waterfall_verify_email(email="fake@nope.com")
            assert result["valid"] is False
            assert result["safe_to_send"] is False
