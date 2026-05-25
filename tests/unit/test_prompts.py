"""
Tests for deepline_gtm_agent.prompts and managed_agent.setup SYSTEM_PROMPT.

Validates that both prompts contain all required policy sections and
critical rules from the 20-gap fix. No external dependencies.
"""

import sys
from unittest.mock import MagicMock

for mod in ["deepagents", "langchain_core", "langchain_core.tools", "anthropic"]:
    sys.modules.setdefault(mod, MagicMock())

import pytest
from deepline_gtm_agent.prompts import GTM_SYSTEM_PROMPT


# We import managed_agent.setup lazily to avoid side effects
def get_managed_prompt():
    import importlib, sys
    # Ensure anthropic is mocked before import
    sys.modules["anthropic"] = MagicMock()
    spec = importlib.util.spec_from_file_location(
        "managed_agent.setup",
        "/tmp/deepline-gtm-agent-fix/managed_agent/setup.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# LangGraph GTM_SYSTEM_PROMPT
# ---------------------------------------------------------------------------

class TestGTMSystemPrompt:
    """Validate GTM_SYSTEM_PROMPT covers all 20 gap requirements."""

    # Gap #1 — Primary interface clarity
    def test_mentions_deepline_enrich_for_batch(self):
        assert "deepline enrich" in GTM_SYSTEM_PROMPT

    def test_warns_against_looping_deepline_call(self):
        text = GTM_SYSTEM_PROMPT.lower()
        assert "loop" in text or "batch" in text

    # Gap #3 — Session UI (LangGraph prompt uses deepline_call("session_start", ...) interface)
    def test_session_ui_mandatory(self):
        # LangGraph agent calls via deepline_call tool, not CLI
        assert "session_start" in GTM_SYSTEM_PROMPT or "session start" in GTM_SYSTEM_PROMPT
        assert "MANDATORY" in GTM_SYSTEM_PROMPT or "mandatory" in GTM_SYSTEM_PROMPT.lower()

    def test_session_status_mentioned(self):
        assert "session_status" in GTM_SYSTEM_PROMPT or "session status" in GTM_SYSTEM_PROMPT

    # Gap #4 — Approval gate
    def test_pilot_rows_mentioned(self):
        assert "0:1" in GTM_SYSTEM_PROMPT or "rows 0:1" in GTM_SYSTEM_PROMPT

    def test_approval_gate_mentioned(self):
        text = GTM_SYSTEM_PROMPT.lower()
        assert "approval" in text or "pilot" in text

    def test_no_auto_proceed(self):
        text = GTM_SYSTEM_PROMPT.lower()
        assert "never auto" in text or "wait for" in text or "approval" in text

    # Gap #6 — Sales Navigator
    def test_sales_navigator_mentioned(self):
        assert "Sales Navigator" in GTM_SYSTEM_PROMPT or "sales/lead" in GTM_SYSTEM_PROMPT

    # Gap #7 — Provider ordering (wiza first)
    def test_wiza_mentioned_first_in_waterfall(self):
        wiza_pos = GTM_SYSTEM_PROMPT.find("wiza")
        dropleads_pos = GTM_SYSTEM_PROMPT.find("dropleads")
        hunter_pos = GTM_SYSTEM_PROMPT.find("hunter")
        assert wiza_pos != -1, "wiza not mentioned"
        assert dropleads_pos != -1, "dropleads not mentioned"
        assert hunter_pos != -1, "hunter not mentioned"
        assert wiza_pos < hunter_pos, "wiza should appear before hunter in waterfall"

    def test_free_tier_1_mentioned(self):
        text = GTM_SYSTEM_PROMPT.lower()
        assert "free" in text or "tier 1" in text or "no-cost" in text

    # Gap #8, #9 — Count-first + over-provision
    def test_over_provision_mentioned(self):
        assert "1.4" in GTM_SYSTEM_PROMPT or "over-provision" in GTM_SYSTEM_PROMPT

    def test_count_first_mentioned(self):
        text = GTM_SYSTEM_PROMPT.lower()
        assert "limit" in text and ("1" in text)  # limit:1 count-first pattern

    # Gap #10 — CrustData rules
    def test_iso3_country_codes_mentioned(self):
        assert "ISO-3" in GTM_SYSTEM_PROMPT or "USA" in GTM_SYSTEM_PROMPT

    def test_crunchbase_categories_mentioned(self):
        assert "crunchbase_categories" in GTM_SYSTEM_PROMPT

    def test_autocomplete_required_before_search(self):
        assert "autocomplete" in GTM_SYSTEM_PROMPT

    # Gap #11 — Role-based search
    def test_no_exact_title_rule(self):
        text = GTM_SYSTEM_PROMPT.lower()
        assert "exact title" in text or "never search by exact" in text or "never filter by exact" in text

    def test_seniority_filter_mentioned(self):
        assert "job_level" in GTM_SYSTEM_PROMPT or "seniority" in GTM_SYSTEM_PROMPT

    # Gap #13 — Personal vs work email
    def test_personal_vs_work_email_mentioned(self):
        text = GTM_SYSTEM_PROMPT.lower()
        assert "personal" in text and "work" in text

    # Gap #14 — Post-enrichment stats
    def test_fill_rate_stats_format(self):
        assert "fill" in GTM_SYSTEM_PROMPT.lower() or "Y contacts" in GTM_SYSTEM_PROMPT

    # Gap #16 — Billing
    def test_billing_balance_mentioned(self):
        assert "billing balance" in GTM_SYSTEM_PROMPT or "billing_balance" in GTM_SYSTEM_PROMPT

    # Gap #17 — Feedback
    def test_provide_feedback_mentioned(self):
        assert "provide-feedback" in GTM_SYSTEM_PROMPT or "provide_feedback" in GTM_SYSTEM_PROMPT

    # Gap #18 — Working directory
    def test_working_directory_not_tmp(self):
        # Prompt may mention /tmp in the context of "No /tmp writes" — that's fine
        text = GTM_SYSTEM_PROMPT.lower()
        if "/tmp" in text:
            assert "no /tmp" in text or "never /tmp" in text or "not /tmp" in text

    def test_deepline_data_dir_mentioned(self):
        assert "deepline/data" in GTM_SYSTEM_PROMPT

    # Gap #19 — CSV policy
    def test_csv_show_summary_mentioned(self):
        assert "csv show" in GTM_SYSTEM_PROMPT

    def test_no_large_csv_reads_rule(self):
        text = GTM_SYSTEM_PROMPT.lower()
        assert "never read" in text or "no large csv" in text or "csv show" in text

    # Gap #20 — deeplineagent output path
    def test_result_result_object_mentioned(self):
        assert "result.result.object" in GTM_SYSTEM_PROMPT

    # Output format
    def test_slack_format_instructions(self):
        assert "*single asterisk*" in GTM_SYSTEM_PROMPT or "single asterisk" in GTM_SYSTEM_PROMPT

    def test_credentials_missing_handling(self):
        assert "CREDENTIALS_MISSING" in GTM_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Managed Agent SYSTEM_PROMPT
# ---------------------------------------------------------------------------

class TestManagedAgentSystemPrompt:
    """Validate managed_agent/setup.py SYSTEM_PROMPT covers all gaps."""

    @pytest.fixture(scope="class")
    def prompt(self):
        return get_managed_prompt()

    # Bootstrap
    def test_bootstrap_block_present(self, prompt):
        assert "mkdir -p" in prompt
        assert "deepline auth status" in prompt

    def test_bootstrap_creates_deepline_data(self, prompt):
        assert "~/deepline/data" in prompt

    def test_node_options_proxy(self, prompt):
        assert "NODE_OPTIONS" in prompt
        assert "--use-env-proxy" in prompt

    # Gap #3 — Session UI
    def test_session_start_mandatory(self, prompt):
        assert "deepline session start" in prompt
        assert "MANDATORY" in prompt or "mandatory" in prompt.lower()

    def test_session_status_message(self, prompt):
        assert "deepline session status" in prompt

    def test_session_output(self, prompt):
        assert "deepline session output" in prompt

    # Gap #4 — Approval gate
    def test_pilot_rows_0_1(self, prompt):
        assert "--rows 0:1" in prompt

    def test_approval_required(self, prompt):
        text = prompt.lower()
        assert "approval" in text or "never auto" in text

    # Gap #5 — Enrich syntax
    def test_deepline_enrich_in_cli_reference(self, prompt):
        assert "deepline enrich" in prompt
        assert "--with" in prompt

    def test_with_waterfall_flag(self, prompt):
        assert "--with-waterfall" in prompt

    # Gap #6 — Sales Navigator
    def test_sales_navigator(self, prompt):
        assert "Sales Navigator" in prompt or "sales/lead" in prompt

    # Gap #7 — Wiza first
    def test_wiza_tier1(self, prompt):
        wiza_pos = prompt.find("wiza")
        dropleads_pos = prompt.find("dropleads")
        hunter_pos = prompt.find("hunter")
        assert wiza_pos != -1
        assert wiza_pos < hunter_pos

    def test_tier1_free_labeled(self, prompt):
        text = prompt.lower()
        assert "tier 1" in text or "free" in text

    # Gap #8, #9 — Patterns
    def test_over_provision_1_4(self, prompt):
        assert "1.4" in prompt

    # Gap #10 — CrustData
    def test_iso3_in_managed_prompt(self, prompt):
        assert "ISO-3" in prompt
        assert "USA" in prompt

    def test_crunchbase_categories(self, prompt):
        assert "crunchbase_categories" in prompt

    def test_employee_count_range(self, prompt):
        assert "employee_count_range" in prompt

    # Gap #11 — Role-based search
    def test_no_exact_title_rule(self, prompt):
        text = prompt.lower()
        assert "exact title" in text or "never filter" in text

    # Gap #13 — Personal vs work
    def test_personal_vs_work(self, prompt):
        text = prompt.lower()
        assert "personal" in text and "work" in text

    # Gap #14 — Validation
    def test_fill_rate_reporting(self, prompt):
        assert "fill" in prompt.lower() or "catch-all" in prompt

    # Gap #15 — Consent/approval gate
    def test_never_auto_proceed(self, prompt):
        text = prompt.lower()
        assert "never auto" in text or "never proceed" in text

    # Gap #16 — Billing
    def test_billing_balance_command(self, prompt):
        assert "deepline billing balance" in prompt

    def test_billing_usage_command(self, prompt):
        assert "deepline billing usage" in prompt

    def test_billing_limit_command(self, prompt):
        assert "deepline billing limit" in prompt

    def test_low_balance_warning(self, prompt):
        assert "100 credits" in prompt

    # Gap #17 — Feedback
    def test_provide_feedback_command(self, prompt):
        assert "deepline provide-feedback" in prompt

    # Gap #18 — Working directory
    def test_never_tmp(self, prompt):
        text = prompt.lower()
        assert "/tmp" not in prompt or "never" in text

    def test_deepline_data_slug(self, prompt):
        assert "~/deepline/data" in prompt

    # Gap #19 — CSV policy
    def test_csv_show_summary(self, prompt):
        assert "deepline csv show" in prompt
        assert "--summary" in prompt

    def test_no_large_csv_reads(self, prompt):
        text = prompt.lower()
        assert "never read" in text or "never read large" in text

    # Gap #20 — deeplineagent output
    def test_result_result_object(self, prompt):
        assert "result.result.object" in prompt

    # Plays
    def test_plays_list_mentioned(self, prompt):
        assert "deepline plays list" in prompt

    # Slack format
    def test_slack_format_section(self, prompt):
        assert "Slack" in prompt
        # Slack bold is single asterisk
        text = prompt
        assert "single asterisk" in text or "*single*" in text or "*bold*" in text.lower()

    def test_no_markdown_links_in_slack(self, prompt):
        text = prompt.lower()
        assert "no [md]" in text or "no ## headers" in text or "no **double" in text
