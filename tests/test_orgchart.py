"""Tests for orgchart hierarchy inference module."""

import sys
import os
import importlib

import pytest

# Import orgchart directly to avoid heavy deps in __init__.py
_pkg_dir = os.path.join(os.path.dirname(__file__), os.pardir, "deepline_gtm_agent")
_spec = importlib.util.spec_from_file_location(
    "deepline_gtm_agent.orgchart",
    os.path.join(_pkg_dir, "orgchart.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SENIORITY_LABELS = _mod.SENIORITY_LABELS
SENIORITY_ORDER = _mod.SENIORITY_ORDER
assign_team = _mod.assign_team
build_hierarchy = _mod.build_hierarchy
classify_seniority = _mod.classify_seniority
estimate_seniority_from_experience = _mod.estimate_seniority_from_experience
extract_team_from_title = _mod.extract_team_from_title
extract_teams_from_jobs = _mod.extract_teams_from_jobs
find_direct_reports = _mod.find_direct_reports
find_likely_manager = _mod.find_likely_manager
find_peers = _mod.find_peers
seniority_rank = _mod.seniority_rank
slugify = _mod.slugify


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _person(
    name: str,
    seniority: str,
    team: str = "",
    city: str = "",
    country: str = "",
    total_exp: int = 0,
) -> dict:
    return {
        "slug": slugify(name),
        "name": name,
        "seniority": seniority,
        "team": team,
        "city": city,
        "country": country,
        "total_exp": total_exp,
    }


# ---------------------------------------------------------------------------
# TestSlugify
# ---------------------------------------------------------------------------

class TestSlugify:
    def test_basic(self):
        assert slugify("Jane Doe") == "jane-doe"

    def test_special_chars(self):
        assert slugify("O'Brien-Smith") == "obrien-smith"

    def test_extra_spaces(self):
        assert slugify("  John   Smith  ") == "john-smith"

    def test_mixed_case(self):
        assert slugify("ALICE BOB") == "alice-bob"


# ---------------------------------------------------------------------------
# TestClassifySeniority
# ---------------------------------------------------------------------------

class TestClassifySeniority:
    def test_cto(self):
        assert classify_seniority("Chief Technology Officer") == "cto"

    def test_cto_abbrev(self):
        assert classify_seniority("CTO") == "cto"

    def test_svp(self):
        assert classify_seniority("SVP of Engineering") == "svp"

    def test_senior_vice_president(self):
        assert classify_seniority("Senior Vice President, Sales") == "svp"

    def test_vp(self):
        assert classify_seniority("Vice President of Product") == "vp"

    def test_vp_word_boundary(self):
        assert classify_seniority("VP Engineering") == "vp"

    def test_sr_director(self):
        assert classify_seniority("Senior Director of Engineering") == "sr-director"

    def test_director(self):
        assert classify_seniority("Director of Engineering") == "director"

    def test_head_of(self):
        assert classify_seniority("Head of Engineering") == "director"

    def test_head_comma(self):
        assert classify_seniority("Head, Product") == "director"

    def test_head_start(self):
        assert classify_seniority("Head Engineering") == "director"

    def test_sr_manager(self):
        assert classify_seniority("Senior Manager, DevOps") == "sr-manager"

    def test_group_product_manager(self):
        assert classify_seniority("Group Product Manager") == "sr-manager"

    def test_manager(self):
        assert classify_seniority("Engineering Manager") == "manager"

    def test_principal(self):
        assert classify_seniority("Principal Engineer") == "principal"

    def test_staff(self):
        assert classify_seniority("Staff Engineer") == "principal"

    def test_lead(self):
        assert classify_seniority("Tech Lead") == "lead"

    def test_senior(self):
        assert classify_seniority("Senior Software Engineer") == "senior"

    def test_sr_dot(self):
        assert classify_seniority("Sr. Backend Developer") == "senior"

    def test_ic(self):
        assert classify_seniority("Software Engineer") == "ic"

    def test_empty(self):
        assert classify_seniority("") == "ic"


# ---------------------------------------------------------------------------
# TestSeniorityRank
# ---------------------------------------------------------------------------

class TestSeniorityRank:
    def test_ordering(self):
        assert seniority_rank("cto") < seniority_rank("svp")
        assert seniority_rank("svp") < seniority_rank("vp")
        assert seniority_rank("vp") < seniority_rank("sr-director")
        assert seniority_rank("sr-director") < seniority_rank("director")
        assert seniority_rank("director") < seniority_rank("sr-manager")
        assert seniority_rank("sr-manager") < seniority_rank("manager")
        assert seniority_rank("manager") < seniority_rank("principal")
        assert seniority_rank("principal") < seniority_rank("lead")
        assert seniority_rank("lead") < seniority_rank("senior")
        assert seniority_rank("senior") < seniority_rank("ic")

    def test_unknown_returns_max(self):
        assert seniority_rank("unknown") == seniority_rank("ic")

    def test_seniority_order_list(self):
        assert SENIORITY_ORDER[0] == "cto"
        assert SENIORITY_ORDER[-1] == "ic"

    def test_seniority_labels_exist(self):
        for level in SENIORITY_ORDER:
            assert level in SENIORITY_LABELS


# ---------------------------------------------------------------------------
# TestEstimateSeniorityFromExperience
# ---------------------------------------------------------------------------

class TestEstimateSeniorityFromExperience:
    def test_20_plus(self):
        assert estimate_seniority_from_experience(25) == "vp"

    def test_15_to_19(self):
        assert estimate_seniority_from_experience(17) == "director"

    def test_10_to_14(self):
        assert estimate_seniority_from_experience(12) == "manager"

    def test_5_to_9(self):
        assert estimate_seniority_from_experience(7) == "senior"

    def test_0_to_4(self):
        assert estimate_seniority_from_experience(2) == "ic"

    def test_zero(self):
        assert estimate_seniority_from_experience(0) == "ic"


# ---------------------------------------------------------------------------
# TestExtractTeamFromTitle
# ---------------------------------------------------------------------------

class TestExtractTeamFromTitle:
    def test_comma_team(self):
        assert extract_team_from_title("Head of Engineering, Identity") == "Identity"

    def test_filters_suffix(self):
        assert extract_team_from_title("Engineer, Sr") == ""

    def test_filters_roman(self):
        assert extract_team_from_title("Engineer, III") == ""

    def test_no_comma(self):
        assert extract_team_from_title("Software Engineer") == ""


# ---------------------------------------------------------------------------
# TestExtractTeamsFromJobs
# ---------------------------------------------------------------------------

class TestExtractTeamsFromJobs:
    def test_from_team_field(self):
        jobs = [{"title": "Engineer", "team": "Platform"}]
        assert "Platform" in extract_teams_from_jobs(jobs)

    def test_from_department_field(self):
        jobs = [{"title": "Engineer", "department": "Infrastructure"}]
        assert "Infrastructure" in extract_teams_from_jobs(jobs)

    def test_from_title(self):
        jobs = [{"title": "Head of Engineering, Identity"}]
        assert "Identity" in extract_teams_from_jobs(jobs)

    def test_deduplication(self):
        jobs = [
            {"title": "Eng 1", "team": "Platform"},
            {"title": "Eng 2", "team": "Platform"},
        ]
        teams = extract_teams_from_jobs(jobs)
        assert isinstance(teams, set)
        assert len([t for t in teams if t == "Platform"]) == 1


# ---------------------------------------------------------------------------
# TestAssignTeam
# ---------------------------------------------------------------------------

class TestAssignTeam:
    def test_department(self):
        assert assign_team("Engineer", set(), department="Platform") == "Platform"

    def test_title_extraction(self):
        assert assign_team("Head of Engineering, Identity", set()) == "Identity"

    def test_fuzzy_match(self):
        known = {"Engineering", "Sales"}
        assert assign_team("Senior Engineering Manager", known) == "Engineering"

    def test_no_match(self):
        result = assign_team("Software Engineer", set())
        assert result == ""


# ---------------------------------------------------------------------------
# TestFindLikelyManager
# ---------------------------------------------------------------------------

class TestFindLikelyManager:
    def test_finds_one_level_up_same_team(self):
        target = _person("Alice", "senior", team="Platform", city="NYC", country="US")
        mgr = _person("Bob", "lead", team="Platform", city="NYC", country="US", total_exp=10)
        result = find_likely_manager(target, [mgr])
        assert result is not None
        assert result["slug"] == "bob"

    def test_prefers_same_team(self):
        target = _person("Alice", "senior", team="Platform", city="NYC", country="US")
        mgr_same = _person("Bob", "lead", team="Platform", city="SF", country="US", total_exp=8)
        mgr_diff = _person("Carol", "lead", team="Sales", city="NYC", country="US", total_exp=8)
        result = find_likely_manager(target, [mgr_same, mgr_diff])
        assert result["slug"] == "bob"

    def test_returns_none_for_most_senior(self):
        target = _person("Alice", "cto", team="Engineering")
        candidates = [
            _person("Bob", "vp", team="Engineering"),
            _person("Carol", "director", team="Engineering"),
        ]
        result = find_likely_manager(target, candidates)
        assert result is None

    def test_skips_self(self):
        target = _person("Alice", "senior", team="Platform")
        result = find_likely_manager(target, [target])
        assert result is None

    def test_experience_delta_affects_scoring(self):
        target = _person("Alice", "senior", team="Platform", total_exp=3)
        mgr_exp = _person("Bob", "lead", team="Platform", total_exp=15)
        mgr_no_exp = _person("Carol", "lead", team="Platform", total_exp=4)
        result = find_likely_manager(target, [mgr_exp, mgr_no_exp])
        assert result["slug"] == "bob"

    def test_returns_none_below_threshold(self):
        target = _person("Alice", "senior", team="Platform", city="NYC", country="US")
        # Same or lower seniority -> should skip
        candidate = _person("Bob", "senior", team="Sales", city="SF", country="UK")
        result = find_likely_manager(target, [candidate])
        assert result is None


# ---------------------------------------------------------------------------
# TestFindPeers
# ---------------------------------------------------------------------------

class TestFindPeers:
    def test_same_seniority(self):
        alice = _person("Alice", "senior", team="Platform")
        bob = _person("Bob", "senior", team="Platform")
        carol = _person("Carol", "lead", team="Platform")
        peers = find_peers(alice, [alice, bob, carol])
        slugs = [p["slug"] for p in peers]
        assert "bob" in slugs
        assert "carol" not in slugs

    def test_excludes_self(self):
        alice = _person("Alice", "senior", team="Platform")
        peers = find_peers(alice, [alice])
        assert len(peers) == 0


# ---------------------------------------------------------------------------
# TestFindDirectReports
# ---------------------------------------------------------------------------

class TestFindDirectReports:
    def test_one_level_below_same_team(self):
        mgr = _person("Bob", "lead", team="Platform")
        alice = _person("Alice", "senior", team="Platform")
        reports = find_direct_reports(mgr, [mgr, alice])
        assert any(r["slug"] == "alice" for r in reports)

    def test_excludes_gap_gt_2(self):
        vp = _person("VP", "vp", team="Platform")
        ic = _person("IC", "ic", team="Platform")
        reports = find_direct_reports(vp, [vp, ic])
        assert len(reports) == 0

    def test_gap_of_1_no_team(self):
        mgr = _person("Bob", "lead")
        alice = _person("Alice", "senior")
        reports = find_direct_reports(mgr, [mgr, alice])
        assert any(r["slug"] == "alice" for r in reports)


# ---------------------------------------------------------------------------
# TestBuildHierarchy
# ---------------------------------------------------------------------------

class TestBuildHierarchy:
    def _sample_people(self):
        return [
            _person("Eve", "vp", team="Engineering", city="NYC", country="US", total_exp=20),
            _person("Dan", "director", team="Engineering", city="NYC", country="US", total_exp=15),
            _person("Bob", "manager", team="Platform", city="NYC", country="US", total_exp=10),
            _person("Alice", "senior", team="Platform", city="NYC", country="US", total_exp=5),
            _person("Carol", "senior", team="Platform", city="NYC", country="US", total_exp=4),
        ]

    def test_complete_chart(self):
        people = self._sample_people()
        result = build_hierarchy("bob", people)
        assert "root" in result
        assert "target" in result
        assert result["target"] == "bob"
        assert "edges" in result
        assert "groups" in result

    def test_bob_has_parent(self):
        people = self._sample_people()
        result = build_hierarchy("bob", people)
        edges = result["edges"]
        # Bob should appear as a child of someone
        children_lists = [c for c in edges.values()]
        all_children = [slug for lst in children_lists for slug in lst]
        assert "bob" in all_children

    def test_root_is_most_senior(self):
        people = self._sample_people()
        result = build_hierarchy("bob", people)
        # Eve is the VP, the most senior
        assert result["root"] == "eve"

    def test_label_format(self):
        people = self._sample_people()
        result = build_hierarchy("bob", people)
        assert "Bob" in result["label"]
