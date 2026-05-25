"""
Tests for deepline_gtm_agent.formatting — md_to_slack and truncate_for_slack.

These are pure unit tests with no external dependencies.
"""

import pytest
from deepline_gtm_agent.formatting import md_to_slack, truncate_for_slack


# ---------------------------------------------------------------------------
# md_to_slack — bold
# ---------------------------------------------------------------------------

class TestMdToSlackBold:
    def test_double_asterisk_to_single(self):
        assert md_to_slack("**hello**") == "*hello*"

    def test_double_underscore_to_bold(self):
        assert md_to_slack("__world__") == "*world*"

    def test_single_asterisk_unchanged(self):
        # Single asterisk is already Slack bold — must not be double-processed
        assert md_to_slack("*already slack*") == "*already slack*"

    def test_bold_mid_sentence(self):
        result = md_to_slack("This is **important** text")
        assert result == "This is *important* text"

    def test_multiple_bold_spans(self):
        result = md_to_slack("**a** and **b**")
        assert "*a*" in result and "*b*" in result

    def test_triple_asterisk_bold_italic_to_slack_bold(self):
        """***text*** (markdown bold+italic) must become *text* (Slack bold), not **text**."""
        result = md_to_slack("***Morgan J Ingram***")
        assert result == "*Morgan J Ingram*"

    def test_triple_asterisk_in_sentence(self):
        result = md_to_slack("Top Result: ***Morgan J Ingram*** — Sales Coach")
        assert "*Morgan J Ingram*" in result
        assert "**" not in result  # no residual double-asterisks

    def test_triple_asterisk_multiple(self):
        result = md_to_slack("***Alpha*** and ***Beta***")
        assert "*Alpha*" in result
        assert "*Beta*" in result
        assert "***" not in result  # no triple asterisks survive


# ---------------------------------------------------------------------------
# md_to_slack — links
# ---------------------------------------------------------------------------

class TestMdToSlackLinks:
    def test_markdown_link_to_slack(self):
        assert md_to_slack("[Click here](https://example.com)") == "<https://example.com|Click here>"

    def test_slack_link_passthrough(self):
        # Slack-format links should not be mangled
        text = "<https://example.com|Label>"
        result = md_to_slack(text)
        assert result == text

    def test_link_in_sentence(self):
        result = md_to_slack("See [the docs](https://docs.deepline.com) for details")
        assert "<https://docs.deepline.com|the docs>" in result

    def test_bare_url_unchanged(self):
        url = "https://deepline.com"
        result = md_to_slack(url)
        assert url in result


# ---------------------------------------------------------------------------
# md_to_slack — headers
# ---------------------------------------------------------------------------

class TestMdToSlackHeaders:
    def test_h1_to_bold(self):
        result = md_to_slack("# My Header")
        assert result == "*My Header*"

    def test_h2_to_bold(self):
        result = md_to_slack("## Section Title")
        assert result == "*Section Title*"

    def test_h3_to_bold(self):
        result = md_to_slack("### Subsection")
        assert result == "*Subsection*"

    def test_header_after_text_gets_newline(self):
        # "Done.## Title" should not produce "Done.*Title*"
        result = md_to_slack("Done.\n## Title")
        assert "Done." in result
        assert "*Title*" in result
        # They should not be smashed together
        assert "Done.*Title*" not in result

    def test_multiple_headers(self):
        text = "## First\nsome text\n## Second"
        result = md_to_slack(text)
        assert "*First*" in result
        assert "*Second*" in result


# ---------------------------------------------------------------------------
# md_to_slack — bullets
# ---------------------------------------------------------------------------

class TestMdToSlackBullets:
    def test_dash_bullet(self):
        result = md_to_slack("- item one")
        assert result == "• item one"

    def test_asterisk_bullet(self):
        result = md_to_slack("* item two")
        assert result == "• item two"

    def test_multiple_bullets(self):
        text = "- first\n- second\n- third"
        result = md_to_slack(text)
        lines = result.strip().split("\n")
        assert all(l.startswith("•") for l in lines if l.strip())

    def test_bullet_already_slack(self):
        # Already-Slack bullets should not be double-converted
        text = "• existing bullet"
        result = md_to_slack(text)
        assert result == "• existing bullet"
        assert "• •" not in result


# ---------------------------------------------------------------------------
# md_to_slack — horizontal rules
# ---------------------------------------------------------------------------

class TestMdToSlackHR:
    def test_triple_dash_removed(self):
        result = md_to_slack("Before\n---\nAfter")
        assert "---" not in result
        assert "Before" in result
        assert "After" in result

    def test_triple_asterisk_removed(self):
        result = md_to_slack("Before\n***\nAfter")
        assert "***" not in result


# ---------------------------------------------------------------------------
# md_to_slack — blockquotes
# ---------------------------------------------------------------------------

class TestMdToSlackBlockquotes:
    def test_blockquote_stripped(self):
        result = md_to_slack("> quoted text")
        assert ">" not in result
        assert "quoted text" in result

    def test_multi_line_blockquote(self):
        text = "> line one\n> line two"
        result = md_to_slack(text)
        assert ">" not in result


# ---------------------------------------------------------------------------
# md_to_slack — strikethrough
# ---------------------------------------------------------------------------

class TestMdToSlackStrikethrough:
    def test_strikethrough_converted(self):
        result = md_to_slack("~~old text~~")
        assert result == "~old text~"


# ---------------------------------------------------------------------------
# md_to_slack — code blocks
# ---------------------------------------------------------------------------

class TestMdToSlackCodeBlocks:
    def test_code_block_preserved(self):
        text = "```\ndeepline enrich --input leads.csv\n```"
        result = md_to_slack(text)
        assert "deepline enrich --input leads.csv" in result
        assert "```" in result  # backticks preserved

    def test_code_block_not_transformed(self):
        # Content inside code blocks should not be converted
        text = "```\n**bold** and [link](url)\n```"
        result = md_to_slack(text)
        assert "**bold**" in result  # not converted inside code block

    def test_inline_code_preserved(self):
        text = "Run `deepline enrich` to start"
        result = md_to_slack(text)
        assert "`deepline enrich`" in result


# ---------------------------------------------------------------------------
# md_to_slack — tables
# ---------------------------------------------------------------------------

class TestMdToSlackTables:
    def test_simple_table_converted(self):
        text = "| Name | Email |\n|---|---|\n| Jane | jane@acme.com |"
        result = md_to_slack(text)
        assert "Jane" in result
        assert "jane@acme.com" in result
        # Table separators should be gone
        assert "|---|" not in result

    def test_table_headers_bolded(self):
        text = "| Name | Email |\n|---|---|\n| Jane | jane@acme.com |"
        result = md_to_slack(text)
        # For small tables (<=3 cols), uses key:value format with bold headers
        assert "*Name:*" in result or "*Name*" in result

    def test_wide_table_converted(self):
        text = "| A | B | C | D |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |"
        result = md_to_slack(text)
        assert "1" in result and "4" in result


# ---------------------------------------------------------------------------
# md_to_slack — composite / realistic output
# ---------------------------------------------------------------------------

class TestMdToSlackComposite:
    def test_typical_person_result(self):
        text = "## Jane Doe — VP Sales\n\n**Email:** jane@acme.com\n\n[LinkedIn](https://linkedin.com/in/jane)"
        result = md_to_slack(text)
        assert "*Jane Doe — VP Sales*" in result
        assert "*Email:*" in result
        assert "<https://linkedin.com/in/jane|LinkedIn>" in result

    def test_empty_string(self):
        assert md_to_slack("") == ""

    def test_none_handled_by_caller(self):
        # The function expects a string; callers guard for None
        assert md_to_slack("") == ""

    def test_no_excessive_blank_lines(self):
        text = "Line 1\n\n\n\n\nLine 2"
        result = md_to_slack(text)
        assert "\n\n\n" not in result

    def test_slack_bold_not_double_converted(self):
        # Agent outputs Slack format; converter should be idempotent
        text = "*Jane Doe* — VP Sales at Acme\n• jane@acme.com\n• <https://linkedin.com/in/jane|LinkedIn>"
        result = md_to_slack(text)
        assert result == text.strip()


# ---------------------------------------------------------------------------
# truncate_for_slack
# ---------------------------------------------------------------------------

class TestTruncateForSlack:
    def test_short_message_unchanged(self):
        text = "Hello world"
        assert truncate_for_slack(text) == [text]

    def test_long_message_split(self):
        # Create a message over 3900 chars
        para = "x" * 100 + "\n\n"
        text = para * 50  # 5100 chars
        chunks = truncate_for_slack(text)
        assert len(chunks) > 1
        assert all(len(c) <= 3900 for c in chunks)

    def test_all_content_preserved(self):
        paras = [f"paragraph {i}" for i in range(60)]
        text = "\n\n".join(paras)
        chunks = truncate_for_slack(text)
        full = " ".join(chunks)
        for para in paras:
            assert para in full

    def test_custom_max_len(self):
        text = "short"
        assert truncate_for_slack(text, max_len=100) == [text]

    def test_exact_boundary(self):
        text = "a" * 3900
        chunks = truncate_for_slack(text)
        assert len(chunks) == 1
        assert chunks[0] == text
