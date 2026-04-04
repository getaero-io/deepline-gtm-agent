"""Org chart hierarchy inference from a flat list of people.

Takes people with title, team, location, and experience data and infers
organizational hierarchy: managers, peers, and direct reports.
"""

from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SENIORITY_ORDER: list[str] = [
    "cto",
    "svp",
    "vp",
    "sr-director",
    "director",
    "sr-manager",
    "manager",
    "principal",
    "lead",
    "senior",
    "ic",
]

SENIORITY_LABELS: dict[str, str] = {
    "cto": "CTO / Chief Technology Officer",
    "svp": "Senior Vice President",
    "vp": "Vice President",
    "sr-director": "Senior Director",
    "director": "Director / Head",
    "sr-manager": "Senior Manager",
    "manager": "Manager",
    "principal": "Principal / Staff",
    "lead": "Lead",
    "senior": "Senior",
    "ic": "Individual Contributor",
}

_SENIORITY_RANK: dict[str, int] = {level: i for i, level in enumerate(SENIORITY_ORDER)}


# ---------------------------------------------------------------------------
# Core utilities
# ---------------------------------------------------------------------------


def slugify(name: str) -> str:
    """Convert a name to a URL-friendly slug. 'Jane Doe' -> 'jane-doe'."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def classify_seniority(title: str) -> str:
    """Map a job title to a seniority level string."""
    t = title.lower().strip()
    if not t:
        return "ic"

    # Order matters: first match wins.
    if ("chief" in t and "technology" in t) or re.search(r"\bcto\b", t):
        return "cto"
    if "svp" in t or "senior vice president" in t:
        return "svp"
    if "vice president" in t or re.search(r"\bvp\b", t):
        return "vp"
    if "senior director" in t:
        return "sr-director"
    if "head of" in t or "head," in t or t.startswith("head ") or "director" in t:
        return "director"
    if "senior manager" in t or "group product manager" in t:
        return "sr-manager"
    if "manager" in t:
        return "manager"
    if "principal" in t or "staff" in t:
        return "principal"
    if "lead" in t:
        return "lead"
    if "senior" in t or "sr." in t:
        return "senior"
    return "ic"


def seniority_rank(seniority: str) -> int:
    """Return numeric rank for a seniority level (lower = more senior)."""
    return _SENIORITY_RANK.get(seniority, _SENIORITY_RANK["ic"])


# ---------------------------------------------------------------------------
# Team extraction
# ---------------------------------------------------------------------------

_SUFFIX_FILTER = re.compile(r"^(sr|jr|ii|iii|iv|v|senior|junior)$", re.IGNORECASE)


def extract_team_from_title(title: str) -> str:
    """Extract team from title text after a comma, filtering out suffixes."""
    if "," not in title:
        return ""
    after_comma = title.split(",", 1)[1].strip()
    if _SUFFIX_FILTER.match(after_comma):
        return ""
    return after_comma


def extract_teams_from_jobs(job_listings: list[dict]) -> set[str]:
    """Extract unique team names from job listing dicts."""
    teams: set[str] = set()
    for job in job_listings:
        if job.get("team"):
            teams.add(job["team"])
        if job.get("department"):
            teams.add(job["department"])
        title_team = extract_team_from_title(job.get("title", ""))
        if title_team:
            teams.add(title_team)
    return teams


def assign_team(title: str, known_teams: set[str], department: str = "") -> str:
    """Assign a team using department, title extraction, or fuzzy match."""
    if department:
        return department
    title_team = extract_team_from_title(title)
    if title_team:
        return title_team
    # Fuzzy: check if any known team name appears in the title
    t_lower = title.lower()
    for team in known_teams:
        if team.lower() in t_lower:
            return team
    return ""


# ---------------------------------------------------------------------------
# Experience-based seniority estimation
# ---------------------------------------------------------------------------


def estimate_seniority_from_experience(total_years: int) -> str:
    """Estimate seniority level from total years of experience (fallback)."""
    if total_years >= 20:
        return "vp"
    if total_years >= 15:
        return "director"
    if total_years >= 10:
        return "manager"
    if total_years >= 5:
        return "senior"
    return "ic"


# ---------------------------------------------------------------------------
# Manager prediction (multi-feature scoring)
# ---------------------------------------------------------------------------


def find_likely_manager(target: dict, candidates: list[dict]) -> Optional[dict]:
    """Find the most likely manager for *target* from *candidates*.

    Returns the highest-scoring candidate or None if no candidate exceeds
    the minimum threshold.
    """
    target_rank = seniority_rank(target["seniority"])
    best: Optional[dict] = None
    best_score = 0

    for c in candidates:
        # Skip self
        if c["slug"] == target["slug"]:
            continue

        c_rank = seniority_rank(c["seniority"])
        gap = target_rank - c_rank  # positive means candidate is more senior

        if gap <= 0:
            continue  # same or below

        # Seniority gap score
        if gap == 1:
            score = 10
        elif gap == 2:
            score = 5
        elif gap == 3:
            score = 2
        else:
            score = 1

        # Team match
        t_team = (target.get("team") or "").lower()
        c_team = (c.get("team") or "").lower()
        if t_team and c_team:
            if t_team == c_team:
                score += 8
            elif t_team in c_team or c_team in t_team:
                score += 3

        # Geo
        t_city = (target.get("city") or "").lower()
        c_city = (c.get("city") or "").lower()
        t_country = (target.get("country") or "").lower()
        c_country = (c.get("country") or "").lower()
        if t_city and c_city and t_city == c_city:
            score += 2
        elif t_country and c_country and t_country == c_country:
            score += 1

        # Experience delta
        exp_delta = (c.get("total_exp") or 0) - (target.get("total_exp") or 0)
        if exp_delta >= 8:
            score += 3
        elif exp_delta >= 3:
            score += 2

        if score > best_score:
            best_score = score
            best = c

    if best_score >= 5:
        return best
    return None


# ---------------------------------------------------------------------------
# Peer and report detection
# ---------------------------------------------------------------------------


def find_peers(target: dict, all_people: list[dict]) -> list[dict]:
    """Find people at the same seniority rank, excluding self."""
    target_rank = seniority_rank(target["seniority"])
    return [
        p
        for p in all_people
        if p["slug"] != target["slug"] and seniority_rank(p["seniority"]) == target_rank
    ]


def find_direct_reports(target: dict, all_people: list[dict]) -> list[dict]:
    """Find people 1-2 levels below target, preferring same team."""
    target_rank = seniority_rank(target["seniority"])
    reports = []
    for p in all_people:
        if p["slug"] == target["slug"]:
            continue
        gap = seniority_rank(p["seniority"]) - target_rank
        if 1 <= gap <= 2:
            reports.append(p)
    return reports


# ---------------------------------------------------------------------------
# Build hierarchy
# ---------------------------------------------------------------------------


def build_hierarchy(target_slug: str, people: list[dict]) -> dict:
    """Build an org chart hierarchy dict from a flat people list.

    Returns:
        {
            "root": "most-senior-slug",
            "target": "target-slug",
            "label": "Company - Org around Target Name",
            "groups": { "slug": "Team Name" },
            "edges": { "parent_slug": ["child1", "child2"] },
        }
    """
    by_slug: dict[str, dict] = {p["slug"]: p for p in people}
    target = by_slug.get(target_slug)
    if target is None:
        raise ValueError(f"Target slug {target_slug!r} not found in people list")

    # -- Walk upward to find root --
    chain: list[dict] = [target]
    visited_slugs: set[str] = {target["slug"]}
    current = target
    while True:
        mgr = find_likely_manager(current, people)
        if mgr is None or mgr["slug"] in visited_slugs:
            break
        chain.append(mgr)
        visited_slugs.add(mgr["slug"])
        current = mgr

    root = chain[-1]

    # -- Find target's peers and direct reports --
    peers = find_peers(target, people)
    reports = find_direct_reports(target, people)

    # -- Build edges --
    edges: dict[str, list[str]] = {}
    included_slugs: set[str] = set()

    # Connect the management chain
    for i in range(len(chain) - 1):
        child = chain[i]
        parent = chain[i + 1]
        edges.setdefault(parent["slug"], [])
        if child["slug"] not in edges[parent["slug"]]:
            edges[parent["slug"]].append(child["slug"])
        included_slugs.add(child["slug"])
        included_slugs.add(parent["slug"])

    # Peers share the same manager as target
    target_mgr = find_likely_manager(target, people)
    if target_mgr:
        for peer in peers:
            edges.setdefault(target_mgr["slug"], [])
            if peer["slug"] not in edges[target_mgr["slug"]]:
                edges[target_mgr["slug"]].append(peer["slug"])
            included_slugs.add(peer["slug"])

    # Direct reports under target
    for report in reports:
        edges.setdefault(target["slug"], [])
        if report["slug"] not in edges[target["slug"]]:
            edges[target["slug"]].append(report["slug"])
        included_slugs.add(report["slug"])

    # If root has no edges yet, still include it
    included_slugs.add(root["slug"])

    # -- Groups --
    groups: dict[str, str] = {}
    for slug in included_slugs:
        person = by_slug.get(slug)
        if person and person.get("team"):
            groups[slug] = person["team"]

    # -- Label --
    target_name = target.get("name", target_slug)
    company = target.get("company", "")
    label = f"{company} - Org around {target_name}".strip(" -")

    return {
        "root": root["slug"],
        "target": target_slug,
        "label": label,
        "groups": groups,
        "edges": edges,
    }
