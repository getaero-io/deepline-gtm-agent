"""
Deepline operations exposed as Deep Agents-compatible tool functions.

Each function follows the Deep Agents convention:
- Plain Python function with a clear docstring
- Type-annotated parameters (auto-generate the tool schema)
- Returns a dict or str that the agent can reason about

Interface guidance
------------------
Single-record lookups (one person): use waterfall_enrich / enrich_person.
  These call deepline_execute (equivalent to deepline tools execute) which is
  fine for one-off operations.

Bulk prospecting/list jobs (5+ requested rows): use build_prospect_list_job.
  It creates a seed CSV, runs a pilot, and returns durable artifacts.

Batch / CSV enrichment on an existing file (5+ records): use batch_enrich.
  This calls `deepline enrich` via subprocess, which has rate limiting,
  Session UI visibility, retry safety, and auto-batching.
  NEVER call waterfall_enrich in a loop over rows — use batch_enrich instead.
"""

import csv
import json
import logging
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Optional
from deepline_gtm_agent.deepline import deepline_execute

logger = logging.getLogger(__name__)


def _normalize_linkedin_url(url: str) -> str:
    """
    Ensure a LinkedIn URL is fully qualified with https://www.linkedin.com prefix.

    Sales Navigator URLs (linkedin.com/sales/...) are NOT canonical and cannot be
    used directly with enrichment providers. Callers should convert these via
    crustdata_person_enrichment before passing to waterfall tools.
    """
    if not url:
        return url
    url = url.strip().rstrip("/")
    if "linkedin.com/sales/" in url:
        logger.warning(
            "Sales Navigator URL detected (%s). Extract canonical URL via "
            "crustdata_person_enrichment before using with waterfall tools.", url
        )
    if url.startswith("https://"):
        return url
    if url.startswith("http://"):
        return "https://" + url[7:]
    if url.startswith("www.linkedin.com"):
        return "https://" + url
    if url.startswith("linkedin.com"):
        return "https://www." + url
    # Already a path like "/in/username" or "in/username"
    if url.startswith("/in/") or url.startswith("in/"):
        slug = url.lstrip("/")
        return f"https://www.linkedin.com/{slug}"
    return url


def _work_dir(slug: str | None = None) -> Path:
    """Return ~/deepline/data/<slug>/ and create it. Never use /tmp."""
    slug = slug or str(int(time.time()))
    d = Path.home() / "deepline" / "data" / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slugify(value: str, fallback: str = "prospect-list") -> str:
    """Create a readable filesystem slug for Deepline job artifacts."""
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-")
    return (slug or fallback)[:80]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    """Write dictionaries to CSV with stable, unioned fieldnames."""
    if not rows:
        raise ValueError("Cannot write an empty CSV")
    ordered_fields: list[str] = []
    for field in fieldnames or []:
        if field not in ordered_fields:
            ordered_fields.append(field)
    for row in rows:
        for key in row:
            if key not in ordered_fields:
                ordered_fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ordered_fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    """Read a seed CSV back into row dictionaries."""
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _csv_summary(path: Path) -> dict[str, Any]:
    """Return lightweight CSV stats without loading large files into the model."""
    if not path.exists():
        return {"exists": False, "row_count": 0}
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        sample_rows = []
        row_count = 0
        for row in reader:
            row_count += 1
            if len(sample_rows) < 3:
                sample_rows.append(row)
        columns = reader.fieldnames or []
    return {
        "exists": True,
        "row_count": row_count,
        "columns": columns,
        "sample_rows": sample_rows,
    }


def _extract_json_array(text: str) -> list[Any] | None:
    """Best-effort extraction for provider outputs that wrap JSON in prose."""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for key in ("companies", "accounts", "rows", "results", "data"):
                value = parsed.get(key)
                if isinstance(value, list):
                    return value
    except (TypeError, json.JSONDecodeError):
        pass

    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


def _coerce_seed_rows(raw: Any) -> list[dict[str, Any]]:
    """Normalize common Deepline/provider response shapes into seed rows."""
    if raw is None:
        return []
    if isinstance(raw, list):
        candidates = raw
    elif isinstance(raw, dict):
        candidates = []
        for key in ("companies", "accounts", "rows", "results", "data"):
            value = raw.get(key)
            if isinstance(value, list):
                candidates = value
                break
            if isinstance(value, dict):
                nested = _coerce_seed_rows(value)
                if nested:
                    return nested
        if not candidates and isinstance(raw.get("output"), str):
            candidates = _extract_json_array(raw["output"]) or []
    elif isinstance(raw, str):
        candidates = _extract_json_array(raw) or []
    else:
        candidates = []

    rows: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        name = (
            item.get("company_name")
            or item.get("name")
            or item.get("company")
            or item.get("organization_name")
        )
        domain = (
            item.get("domain")
            or item.get("company_domain")
            or item.get("website")
            or item.get("url")
        )
        row = dict(item)
        if name:
            row.setdefault("company_name", name)
        if domain:
            domain_text = str(domain).strip()
            domain_text = re.sub(r"^https?://", "", domain_text).split("/")[0]
            row.setdefault("domain", domain_text)
        if row.get("company_name") or row.get("domain"):
            rows.append(row)
    return rows


def _normalize_enrich_column(column: dict[str, Any]) -> dict[str, Any]:
    """Accept older tool_id-shaped specs but emit Deepline enrich's tool key."""
    normalized = dict(column)
    if "tool" not in normalized and "tool_id" in normalized:
        normalized["tool"] = normalized["tool_id"]
    normalized.setdefault("alias", normalized.get("tool") or normalized.get("tool_id") or "enrichment")
    return normalized


# ---------------------------------------------------------------------------
# Person enrichment
# ---------------------------------------------------------------------------


def enrich_person(
    linkedin_url: Optional[str] = None,
    email: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    company_domain: Optional[str] = None,
    company_name: Optional[str] = None,
) -> dict:
    """
    Enrich a person's contact data: work email, phone, job title, LinkedIn.

    Waterfall: Hunter (domain + name) → Crustdata (LinkedIn URL) → Deepline Native enrich_contact.
    At least one of linkedin_url, email, or (first_name + last_name + company) is required.

    Returns a dict with: email, phone, linkedin_url, title, company, location.
    """
    if not any([linkedin_url, email, (first_name and last_name)]):
        return {"error": "Provide linkedin_url, email, or first_name + last_name."}

    if linkedin_url:
        linkedin_url = _normalize_linkedin_url(linkedin_url)

    # Wiza — free first pass, strong US/EU coverage (no cost on miss)
    if linkedin_url:
        try:
            result = deepline_execute("wiza_enrich_person", {"linkedin_url": linkedin_url})
            if result.get("email") or (result.get("data") or {}).get("email"):
                return {"provider": "wiza", **result}
        except Exception as e:
            logger.debug("wiza_enrich_person failed for enrich_person: %s", e)

    # Dropleads — free, good EU/mid-market coverage (no cost on miss)
    if first_name and last_name:
        try:
            dl_payload: dict = {"first_name": first_name, "last_name": last_name}
            if company_domain:
                dl_payload["company_domain"] = company_domain
            if company_name:
                dl_payload["company_name"] = company_name
            result = deepline_execute("dropleads_email_finder", dl_payload)
            if result.get("email") or (result.get("data") or {}).get("email"):
                return {"provider": "dropleads", **result}
        except Exception as e:
            logger.debug("dropleads_email_finder failed for enrich_person: %s", e)

    # Hunter email finder — best for domain + name lookup
    if company_domain and first_name and last_name:
        try:
            result = deepline_execute("hunter_email_finder", {
                "domain": company_domain,
                "first_name": first_name,
                "last_name": last_name,
            })
            if result.get("email"):
                return {"provider": "hunter", **result}
        except Exception as e:
            logger.debug("hunter_email_finder failed for enrich_person: %s", e)

    # Crustdata person enrichment — LinkedIn-native, best when URL is known
    # Correct tool: crustdata_person_enrichment with linkedinProfileUrl param
    if linkedin_url:
        try:
            result = deepline_execute("crustdata_person_enrichment", {"linkedinProfileUrl": linkedin_url})
            if result:
                return {"provider": "crustdata", **result}
        except Exception as e:
            logger.debug("crustdata_person_enrichment failed for enrich_person: %s", e)

    # Deepline Native enrich_contact — single contact enrichment (not prospector)
    # prospector requires a title filter and returns batch results; enrich_contact
    # takes one identity (linkedin + domain, or first + last + domain) and returns
    # a single verified contact record.
    if linkedin_url and company_domain:
        try:
            result = deepline_execute("deepline_native_enrich_contact", {
                "linkedin": linkedin_url,
                "domain": company_domain,
            })
            if result.get("email") or (result.get("data") or {}).get("email"):
                return {"provider": "deepline_native_enrich_contact", **result}
        except Exception as e:
            logger.debug("deepline_native_enrich_contact (linkedin) failed for enrich_person: %s", e)

    if first_name and last_name and company_domain:
        try:
            result = deepline_execute("deepline_native_enrich_contact", {
                "first_name": first_name,
                "last_name": last_name,
                "domain": company_domain,
            })
            if result.get("email") or (result.get("data") or {}).get("email"):
                return {"provider": "deepline_native_enrich_contact", **result}
        except Exception as e:
            logger.debug("deepline_native_enrich_contact (name) failed for enrich_person: %s", e)

    return {"error": "Could not enrich contact — try providing more identifiers."}


# ---------------------------------------------------------------------------
# Prospect search
# ---------------------------------------------------------------------------


def _employee_ranges(size_min: Optional[int], size_max: Optional[int]) -> list[str]:
    """Map integer headcount range to Dropleads bucket strings."""
    buckets = [
        (1, 10, "1-10"),
        (11, 50, "11-50"),
        (51, 200, "51-200"),
        (201, 500, "201-500"),
        (501, 1000, "501-1000"),
        (1001, 5000, "1001-5000"),
        (5001, 10000, "5001-10000"),
        (10001, 10**9, "10000+"),
    ]
    lo = size_min or 1
    hi = size_max or 10**9
    return [label for (blo, bhi, label) in buckets if blo <= hi and bhi >= lo]


_SENIORITY_MAP = {
    "owner": "C-Level",
    "founder": "C-Level",
    "c_suite": "C-Level",
    "vp": "VP",
    "director": "Director",
    "manager": "Manager",
    "individual_contributor": "Senior",
}

# Niche/ambiguous titles that need expansion to get results from Dropleads
# City/state → country mapping for Dropleads (personalCountries accepts country names only)
_LOCATION_TO_COUNTRY: dict[str, str] = {
    # US cities/states
    "new york city": "United States",
    "new york": "United States",
    "nyc": "United States",
    "san francisco": "United States",
    "sf": "United States",
    "bay area": "United States",
    "silicon valley": "United States",
    "los angeles": "United States",
    "la": "United States",
    "chicago": "United States",
    "boston": "United States",
    "seattle": "United States",
    "austin": "United States",
    "miami": "United States",
    "denver": "United States",
    "atlanta": "United States",
    "california": "United States",
    "texas": "United States",
    "new york state": "United States",
    "florida": "United States",
    # UK cities
    "london": "United Kingdom",
    "manchester": "United Kingdom",
    "edinburgh": "United Kingdom",
    # Other
    "toronto": "Canada",
    "vancouver": "Canada",
    "sydney": "Australia",
    "melbourne": "Australia",
    "berlin": "Germany",
    "paris": "France",
    "amsterdam": "Netherlands",
    "stockholm": "Sweden",
    "singapore": "Singapore",
    "dubai": "United Arab Emirates",
    "tel aviv": "Israel",
}

# City names we can use for post-filter hints (returned in search note)
_CITY_KEYWORDS = {
    "new york city", "nyc", "san francisco", "sf", "bay area",
    "los angeles", "chicago", "boston", "seattle", "austin",
    "miami", "london", "berlin", "paris", "toronto", "sydney",
}


def _normalize_location(location: str) -> tuple[str, str | None]:
    """
    Map a city/state/region to a Dropleads-compatible country string.
    Returns (country_for_dropleads, original_city_hint_or_None).
    """
    normalized = location.strip().lower()
    country = _LOCATION_TO_COUNTRY.get(normalized)
    if country:
        # Keep original as hint for the response
        city_hint = location if normalized in _CITY_KEYWORDS else None
        return country, city_hint
    # Already a country name — pass through
    return location, None


_TITLE_EXPANSIONS: dict[str, list[str]] = {
    "gtm engineer": ["GTM Engineer", "Growth Engineer", "Revenue Operations Engineer", "Marketing Engineer"],
    "gtm": ["GTM Engineer", "Growth Engineer", "Go-To-Market"],
    "growth engineer": ["Growth Engineer", "GTM Engineer", "Marketing Engineer", "Revenue Engineer"],
    "ai engineer": ["AI Engineer", "Machine Learning Engineer", "ML Engineer", "Artificial Intelligence Engineer"],
    "llm engineer": ["LLM Engineer", "AI Engineer", "Machine Learning Engineer", "NLP Engineer"],
    "devrel": ["Developer Relations", "Developer Advocate", "DevRel Engineer", "Developer Experience"],
    "revops": ["Revenue Operations", "RevOps", "Sales Operations", "GTM Operations"],
    "data scientist": ["Data Scientist", "Machine Learning Engineer", "AI Researcher", "Research Scientist"],
}


def _expand_title(title: str) -> list[str]:
    """Return a list of title variations for niche/ambiguous titles."""
    normalized = title.lower().strip()
    if normalized in _TITLE_EXPANSIONS:
        return _TITLE_EXPANSIONS[normalized]
    # Check partial matches
    for key, variants in _TITLE_EXPANSIONS.items():
        if key in normalized or normalized in key:
            return [title] + [v for v in variants if v.lower() != normalized]
    return [title]


def search_prospects(
    job_title: Optional[str] = None,
    job_level: Optional[str] = None,
    company_name: Optional[str] = None,
    company_domain: Optional[str] = None,
    person_location: Optional[str] = None,
    company_size_min: Optional[int] = None,
    company_size_max: Optional[int] = None,
    company_industry: Optional[str] = None,
    recently_hired_months: Optional[int] = None,
    limit: int = 10,
) -> dict:
    """
    Search for people (prospects) matching ICP criteria.

    Uses Dropleads (free) as primary provider with automatic title expansion for niche roles.
    When recently_hired_months is set, routes to Icypeas which supports job start-date filtering.
    Falls through to Deepline Native Prospector when a company_domain is provided.

    job_level accepted values: owner, founder, c_suite, vp, director, manager, individual_contributor.
    company_size_min / company_size_max: integer employee counts (e.g. 200, 500).
    company_industry: plain-language industry (e.g. "Software", "SaaS", "Healthcare").
    person_location: country or US state name (e.g. "United States", "California", "New York").
    recently_hired_months: filter to people who started their current role within this many months.

    Returns a list of people with name, title, company, LinkedIn URL, and email (when available).
    """
    # --- Recently hired: route to Icypeas which supports start-date filtering ---
    if recently_hired_months and job_title:
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(days=recently_hired_months * 30)).strftime("%Y-%m-%d")
        try:
            icypeas_payload: dict = {
                "job_title": {"include": _expand_title(job_title)},
                "started_role_after": cutoff,
                "limit": min(limit, 25),
            }
            if person_location:
                # Icypeas accepts city names directly
                icypeas_payload["location"] = {"include": [person_location]}
            result = deepline_execute("icypeas_find_people", icypeas_payload)
            people = (result.get("data") or result).get("people", [])[:limit]
            if people:
                return {
                    "provider": "icypeas",
                    "filter": f"hired after {cutoff}",
                    "count": len(people),
                    "prospects": [
                        {
                            "name": p.get("fullName") or f"{p.get('firstName','')} {p.get('lastName','')}".strip(),
                            "title": p.get("jobTitle"),
                            "company": p.get("companyName"),
                            "linkedin_url": p.get("linkedinUrl"),
                            "email": p.get("email") or None,
                            "location": p.get("location"),
                            "started_role": p.get("startedRole"),
                            "has_email": bool(p.get("email")),
                        }
                        for p in people
                    ],
                }
        except Exception as e:
            logger.debug("icypeas_find_people failed for recently_hired search: %s", e)
        # Fall through to Dropleads without the date filter, noting the limitation
        logger.info("Icypeas miss for recently_hired — falling back to Dropleads without date filter")

    # --- Dropleads primary search ---
    # Expand niche titles to catch more results (e.g. "GTM engineer" → multiple variants)
    title_variants = _expand_title(job_title) if job_title else []

    filters: dict = {}
    if title_variants:
        filters["jobTitles"] = title_variants
    if job_level:
        dl_seniority = _SENIORITY_MAP.get(job_level)
        if dl_seniority:
            filters["seniority"] = [dl_seniority]
    if company_domain:
        filters["companyDomains"] = [company_domain]
    elif company_name:
        filters["companyNames"] = [company_name]
    if person_location:
        # Dropleads personalCountries only accepts country names — map cities/states
        dropleads_country, city_hint = _normalize_location(person_location)
        filters["personalCountries"] = {"include": [dropleads_country]}
        if city_hint:
            filters["_city_hint"] = city_hint  # passed through to response note
    if company_size_min or company_size_max:
        filters["employeeRanges"] = _employee_ranges(company_size_min, company_size_max)
    if company_industry:
        filters["industries"] = [company_industry]

    city_hint = filters.pop("_city_hint", None)

    def _run_dropleads(f: dict) -> list:
        r = deepline_execute("dropleads_search_people", {
            "filters": f,
            "pagination": {"page": 1, "limit": min(limit, 25)},
        })
        return (r.get("data") or r).get("leads", [])[:limit], (r.get("data") or r).get("total", 0)

    industry_dropped = False
    try:
        leads, total = _run_dropleads(filters)
        # Dropleads industry taxonomy is narrow — if 0 results with industry filter, retry without it
        if not leads and "industries" in filters:
            filters_no_industry = {k: v for k, v in filters.items() if k != "industries"}
            leads, total = _run_dropleads(filters_no_industry)
            if leads:
                industry_dropped = True
        if leads:
            notes = []
            if industry_dropped:
                notes.append(f"Dropleads has no exact match for industry '{company_industry}' — searched without industry filter")
            if recently_hired_months:
                notes.append(f"Dropleads has no hire-date filter — results are not filtered to last {recently_hired_months} months")
            if city_hint:
                notes.append(f"Dropleads filters by country only — searched United States broadly, not specifically {city_hint}")
            return {
                "provider": "dropleads",
                "title_variants_tried": title_variants,
                "total": total,
                "count": len(leads),
                "note": "; ".join(notes) if notes else None,
                "prospects": [
                    {
                        "name": lead.get("fullName"),
                        "title": lead.get("title"),
                        "company": lead.get("companyName"),
                        "linkedin_url": lead.get("linkedinUrl"),
                        "email": lead.get("email") or None,
                        "location": lead.get("location"),
                        "company_size": lead.get("companySize"),
                        "industry": lead.get("industry"),
                        "has_email": bool(lead.get("email")),
                    }
                    for lead in leads
                ],
            }
    except Exception as e:
        logger.debug("dropleads_search_people failed for search_prospects: %s", e)

    # --- Deepline Native Prospector fallback (domain-specific, has email) ---
    # Requires title_filters as an array of {name, filter} objects — not title_filter string
    if company_domain and job_title:
        try:
            result = deepline_execute("deepline_native_prospector", {
                "domain": company_domain,
                "title_filters": [{"name": "primary", "filter": job_title}],
                "limit": min(limit, 25),
            })
            contacts = (result.get("result", {}).get("data") or result).get("contacts", [])
            return {
                "provider": "deepline_native_prospector",
                "count": len(contacts),
                "prospects": [
                    {
                        "email": c.get("email"),
                        "linkedin_url": c.get("linkedin"),
                        "phone": c.get("phone"),
                        "has_email": bool(c.get("email")),
                    }
                    for c in contacts
                ],
            }
        except Exception as e:
            logger.debug("deepline_native_prospector failed for search_prospects: %s", e)

    # Final fallback: Icypeas find_people (broader coverage, city-level filters)
    if job_title:
        try:
            icypeas_payload: dict = {
                "job_title": {"include": title_variants or [job_title]},
                "limit": min(limit, 25),
            }
            if person_location:
                icypeas_payload["location"] = {"include": [person_location]}
            if company_industry:
                icypeas_payload["industry"] = {"include": [company_industry]}
            result = deepline_execute("icypeas_find_people", icypeas_payload)
            people = (result.get("data") or result).get("people", [])[:limit]
            if people:
                notes = ["Dropleads had no coverage — results from Icypeas fallback"]
                if city_hint:
                    notes.append(f"filtered to {city_hint}")
                return {
                    "provider": "icypeas_fallback",
                    "title_variants_tried": title_variants,
                    "count": len(people),
                    "note": "; ".join(notes),
                    "prospects": [
                        {
                            "name": p.get("fullName") or f"{p.get('firstName','')} {p.get('lastName','')}".strip(),
                            "title": p.get("jobTitle"),
                            "company": p.get("companyName"),
                            "linkedin_url": p.get("linkedinUrl"),
                            "email": p.get("email") or None,
                            "location": p.get("location"),
                            "has_email": bool(p.get("email")),
                        }
                        for p in people
                    ],
                }
        except Exception as e:
            logger.debug("icypeas_find_people fallback failed: %s", e)

    tips = ["Dropleads and Icypeas had no coverage for this title+filter combination."]
    if city_hint:
        tips.append(f"Dropleads searched country-wide (United States) — cannot filter to {city_hint} specifically.")
    tips.append("Try web_research for a broader search, or use deepline_call with apollo_search_people.")
    return {
        "error": "No results found from any provider.",
        "title_variants_tried": title_variants,
        "filters_used": {k: v for k, v in filters.items() if not k.startswith("_")},
        "tip": " ".join(tips),
    }


# ---------------------------------------------------------------------------
# Company research
# ---------------------------------------------------------------------------


def research_company(
    domain: Optional[str] = None,
    company_name: Optional[str] = None,
) -> dict:
    """
    Research a company: description, industry, headcount, funding, tech stack, location.

    Waterfall: Crustdata (LinkedIn-native, headcount signals) → Exa web research (live, most current).
    Provide domain (e.g. "stripe.com") or company_name.
    """
    if not domain and not company_name:
        return {"error": "Provide domain or company_name."}

    # Crustdata — LinkedIn-native, good headcount signals
    if domain:
        try:
            result = deepline_execute("crustdata_company_enrichment", {"companyDomain": domain, "exactMatch": True})
            if result:
                return {"provider": "crustdata", **result}
        except Exception as e:
            logger.debug("crustdata_company_enrichment failed for research_company: %s", e)

    # Exa web research — live web sources, most current data
    try:
        query = domain or company_name
        result = deepline_execute("exa_research", {
            "instructions": f"Research the company at {query}. Return: full company name, industry, headcount, total funding raised, HQ location, founding year, what the company does (2-3 sentences), notable customers or use cases, and any recent news or signals (hiring, fundraising, expansion).",
            "model": "exa-research-fast",
        })
        summary = (result.get("data") or result).get("output", {})
        if summary:
            return {"provider": "exa_research", "domain": domain, "company_name": company_name, "summary": summary}
    except Exception as e:
        logger.debug("exa_research failed for research_company: %s", e)

    return {"error": f"Could not find company data for {domain or company_name}"}


# ---------------------------------------------------------------------------
# Web research (open-ended)
# ---------------------------------------------------------------------------


def web_research(query: str) -> dict:
    """
    Run open-ended web research via Exa. Use for:
    - Company intelligence not covered by firmographic databases
    - Finding people by name/role when database lookup fails
    - Recent news, funding rounds, job postings, product launches
    - Any question requiring live web data

    Returns a structured research summary with citations.
    """
    try:
        result = deepline_execute("exa_research", {
            "instructions": query,
            "model": "exa-research-fast",
        })
        data = result.get("data") or result
        return {
            "provider": "exa_research",
            "query": query,
            "summary": data.get("output", data),
        }
    except Exception as e:
        return {"error": str(e), "query": query}


# ---------------------------------------------------------------------------
# Waterfall enrichment (Deepline-native)
# ---------------------------------------------------------------------------


def waterfall_enrich(
    linkedin_url: Optional[str] = None,
    email: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    company_domain: Optional[str] = None,
    company_name: Optional[str] = None,
) -> dict:
    """
    Enrich a person using Deepline's native waterfall enrichment.

    Delegates the entire provider waterfall to Deepline's API in a single call —
    Deepline tries multiple providers in sequence and returns the best result.
    Prefer this over enrich_person for bulk enrichment or when you want Deepline
    to handle provider selection automatically.

    At least one of linkedin_url, email, or (first_name + last_name + company) is required.

    Returns a dict with: email, phone, linkedin_url, title, company, location.
    """
    if not any([linkedin_url, email, (first_name and last_name)]):
        return {"error": "Provide linkedin_url, email, or first_name + last_name."}

    if linkedin_url:
        linkedin_url = _normalize_linkedin_url(linkedin_url)

    payload: dict = {}
    if linkedin_url:
        payload["linkedin_url"] = linkedin_url
    if email:
        payload["email"] = email
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name
    if company_domain:
        payload["company_domain"] = company_domain
    if company_name:
        payload["company_name"] = company_name

    # Waterfall: try providers in cost order, stop on first hit.
    # Tier 1 (free/no-cost-on-miss) always runs first.
    # Tier 2 (paid) only runs after Tier 1 miss.

    providers_tried: list[str] = []

    # 0. Wiza — free first pass, strong US/EU coverage (no cost on miss)
    if linkedin_url:
        try:
            result = deepline_execute("wiza_enrich_person", {"linkedin_url": linkedin_url})
            found = result.get("email") or (result.get("data", {}) or {}).get("email")
            providers_tried.append("wiza_enrich_person")
            if found:
                return {"provider": "wiza_enrich_person", "email": found, **result}
        except Exception as e:
            logger.debug("wiza_enrich_person failed: %s", e)

    # 1. Dropleads email finder — free, fast
        dl_payload: dict = {"first_name": first_name, "last_name": last_name}
        if company_domain:
            dl_payload["company_domain"] = company_domain
        if company_name:
            dl_payload["company_name"] = company_name
        try:
            result = deepline_execute("dropleads_email_finder", dl_payload)
            found = result.get("email") or (result.get("data", {}) or {}).get("email")
            providers_tried.append("dropleads_email_finder")
            if found:
                return {"provider": "dropleads_email_finder", "email": found, **result}
        except Exception as e:
            logger.debug("dropleads_email_finder failed: %s", e)

    # 2. Hunter email finder — domain required
    if first_name and last_name and company_domain:
        try:
            result = deepline_execute("hunter_email_finder", {
                "domain": company_domain,
                "first_name": first_name,
                "last_name": last_name,
            })
            found = result.get("email") or (result.get("data", {}) or {}).get("email")
            providers_tried.append("hunter_email_finder")
            if found:
                return {"provider": "hunter_email_finder", "email": found, **result}
        except Exception as e:
            logger.debug("hunter_email_finder failed: %s", e)

    # 3. LeadMagic email finder
    if first_name and last_name:
        lm_payload: dict = {"first_name": first_name, "last_name": last_name}
        if company_domain:
            lm_payload["domain"] = company_domain
        try:
            result = deepline_execute("leadmagic_email_finder", lm_payload)
            found = result.get("email") or (result.get("data", {}) or {}).get("email")
            providers_tried.append("leadmagic_email_finder")
            if found:
                return {"provider": "leadmagic_email_finder", "email": found, **result}
        except Exception as e:
            logger.debug("leadmagic_email_finder failed: %s", e)

    # 4. Deepline native contact enrichment
    native_payload: dict = {}
    if linkedin_url:
        native_payload["linkedin"] = linkedin_url
    if first_name:
        native_payload["first_name"] = first_name
    if last_name:
        native_payload["last_name"] = last_name
    if company_domain:
        native_payload["domain"] = company_domain
    if email:
        native_payload["email"] = email
    if native_payload:
        try:
            result = deepline_execute("deepline_native_enrich_contact", native_payload)
            found = result.get("email") or (result.get("data", {}) or {}).get("email")
            providers_tried.append("deepline_native_enrich_contact")
            if found:
                return {"provider": "deepline_native_enrich_contact", "email": found, **result}
        except Exception as e:
            logger.debug("deepline_native_enrich_contact failed: %s", e)

    # 5. Crustdata person enrichment — LinkedIn URL required
    if linkedin_url:
        try:
            result = deepline_execute("crustdata_person_enrichment", {
                "linkedinProfileUrl": linkedin_url,
            })
            found = result.get("email") or (result.get("data", {}) or {}).get("email")
            providers_tried.append("crustdata_person_enrichment")
            if found:
                return {"provider": "crustdata_person_enrichment", "email": found, **result}
        except Exception as e:
            logger.debug("crustdata_person_enrichment failed: %s", e)

    # 6. Icypeas email search — name + domain or LinkedIn
    # icypeas_email_search is async: returns SCHEDULED with an _id.
    # Poll icypeas_read_results until email is available (up to ~15s).
    if first_name and last_name:
        ic_payload: dict = {"first_name": first_name, "last_name": last_name}
        if company_domain:
            ic_payload["company_domain"] = company_domain
        elif company_name:
            ic_payload["company_name"] = company_name
        try:
            result = deepline_execute("icypeas_email_search", ic_payload)
            providers_tried.append("icypeas_email_search")
            # Check if result is immediate (some Deepline wrappers resolve async internally)
            found = result.get("email") or (result.get("data", {}) or {}).get("email")
            if not found:
                # Poll for async result
                import time as _time
                result_id = result.get("_id") or (result.get("data") or {}).get("_id")
                if result_id:
                    for _ in range(5):
                        _time.sleep(3)
                        try:
                            poll = deepline_execute("icypeas_read_results", {"id": result_id})
                            found = poll.get("email") or (poll.get("data") or {}).get("email")
                            if found:
                                result = poll
                                break
                        except Exception:
                            break
            if found:
                return {"provider": "icypeas_email_search", "email": found, **result}
        except Exception as e:
            logger.debug("icypeas_email_search failed: %s", e)

    # 7. Prospeo person enrichment — LinkedIn URL or name + domain
    prospeo_payload: dict = {}
    if linkedin_url:
        prospeo_payload["linkedin_url"] = linkedin_url
    elif first_name and last_name and company_domain:
        prospeo_payload["first_name"] = first_name
        prospeo_payload["last_name"] = last_name
        prospeo_payload["domain"] = company_domain
    if prospeo_payload:
        try:
            result = deepline_execute("prospeo_person_enrichment", prospeo_payload)
            found = result.get("email") or (result.get("data", {}) or {}).get("email")
            providers_tried.append("prospeo_person_enrichment")
            if found:
                return {"provider": "prospeo_person_enrichment", "email": found, **result}
        except Exception as e:
            logger.debug("prospeo_person_enrichment failed: %s", e)

    # 8. PeopleDataLabs — enrichment by name + company
    if first_name and last_name:
        pdl_payload: dict = {
            "params": {
                "first_name": first_name,
                "last_name": last_name,
            }
        }
        if company_domain:
            pdl_payload["params"]["company"] = company_domain
        elif company_name:
            pdl_payload["params"]["company"] = company_name
        try:
            result = deepline_execute("peopledatalabs_person_enrichment", pdl_payload)
            found = result.get("work_email") or result.get("email") or (result.get("data", {}) or {}).get("work_email")
            providers_tried.append("peopledatalabs_person_enrichment")
            if found:
                return {"provider": "peopledatalabs_person_enrichment", "email": found, **result}
        except Exception as e:
            logger.debug("peopledatalabs_person_enrichment failed: %s", e)

    # 10. Forager person detail lookup — requires LinkedIn public identifier
    # forager_person_role_search is for role/title-based prospecting, not name lookup.
    # For email discovery, forager_person_detail_lookup with reveal_work_emails is correct.
    if linkedin_url:
        import re as _re
        li_match = _re.search(r"linkedin\.com/in/([\w\-]+)", linkedin_url)
        if li_match:
            li_identifier = li_match.group(1)
            try:
                result = deepline_execute("forager_person_detail_lookup", {
                    "linkedin_public_identifier": li_identifier,
                    "reveal_work_emails": True,
                    "reveal_personal_emails": False,
                    "reveal_phone_numbers": False,
                })
                data = result.get("data") or result
                found = (
                    data.get("work_email")
                    or data.get("email")
                    or (data.get("person") or {}).get("work_email")
                )
                providers_tried.append("forager_person_detail_lookup")
                if found:
                    return {"provider": "forager_person_detail_lookup", "email": found, **data}
            except Exception as e:
                logger.debug("forager_person_detail_lookup failed: %s", e)

    return {
        "error": "All waterfall providers exhausted — no email found.",
        "providers_tried": providers_tried,
        "tip": (
            "Tried all 9 providers. "
            "Coverage gaps are common for personal/SMB domains or very senior executives. "
            "Try phone enrichment via Forager (reveal_phones=True) or engage via LinkedIn instead."
        ),
    }


# ---------------------------------------------------------------------------
# Batch enrichment via deepline enrich (correct interface for CSV/list work)
# ---------------------------------------------------------------------------


def batch_enrich(
    input_csv: str,
    columns: Optional[list[dict[str, Any]]] = None,
    output_dir: Optional[str] = None,
    rows: str = "0:1",
    full_run: bool = False,
) -> dict:
    """
    Enrich a CSV file using `deepline enrich` — the correct interface for batch work.

    Unlike waterfall_enrich (which calls providers directly for single records),
    this uses the Deepline enrichment engine which provides:
    - Built-in rate limiting and auto-batching
    - Session UI progress visibility
    - Retry safety on provider failure
    - Full audit trail in CSV lineage

    ALWAYS call with rows="0:1" first (pilot), show the result, then call again
    with full_run=True after user approval.

    Args:
        input_csv: Path to input CSV file.
        columns: List of Deepline enrich column specs using keys such as
            alias, tool, payload, and extract_js. Older tool_id-shaped specs are
            normalized to the current tool key. If None, uses the standard email
            waterfall.
        output_dir: Output directory. Defaults to ~/deepline/data/<timestamp>/.
        rows: Row range to process, e.g. "0:1" for pilot, "0:50" for full run.
        full_run: If True, processes all rows (ignores rows parameter).

    Returns dict with output_csv path, fill_rate stats, and provider summary.
    """
    input_path = Path(input_csv).expanduser()
    if not input_path.exists():
        return {"error": f"Input CSV not found: {input_csv}"}

    # Write to proper working directory — never /tmp
    work = Path(output_dir).expanduser() if output_dir else _work_dir()
    work.mkdir(parents=True, exist_ok=True)
    output_path = work / f"{input_path.stem}_enriched.csv"

    # Default email waterfall columns if none specified
    if not columns:
        columns = [
            {"alias": "wiza_email", "tool": "wiza_enrich_person", "payload": {"linkedin_url": "{{linkedin_url}}"}},
            {"alias": "dropleads_email", "tool": "dropleads_email_finder", "payload": {"first_name": "{{first_name}}", "last_name": "{{last_name}}", "domain": "{{domain}}"}},
            {"alias": "hunter_email", "tool": "hunter_email_finder", "payload": {"first_name": "{{first_name}}", "last_name": "{{last_name}}", "domain": "{{domain}}"}},
            {"alias": "leadmagic_email", "tool": "leadmagic_email_finder", "payload": {"first_name": "{{first_name}}", "last_name": "{{last_name}}", "domain": "{{domain}}"}},
            {"alias": "crustdata_person", "tool": "crustdata_person_enrichment", "payload": {"linkedinProfileUrl": "{{linkedin_url}}"}},
            {"alias": "icypeas_email", "tool": "icypeas_email_search", "payload": {"first_name": "{{first_name}}", "last_name": "{{last_name}}", "domain": "{{domain}}"}},
            {"alias": "prospeo_person", "tool": "prospeo_person_enrichment", "payload": {"first_name": "{{first_name}}", "last_name": "{{last_name}}", "domain": "{{domain}}"}},
            {"alias": "forager_person", "tool": "forager_person_detail_lookup", "payload": {"first_name": "{{first_name}}", "last_name": "{{last_name}}", "domain": "{{domain}}"}},
        ]

    # Build enrich command
    cmd = [
        "deepline", "enrich",
        "--input", str(input_path),
        "--output", str(output_path),
        "--json",
    ]

    # Add each column as --with arg
    for col in columns:
        cmd += ["--with", json.dumps(_normalize_enrich_column(col))]

    # Row range (pilot vs full)
    if not full_run and rows:
        cmd += ["--rows", rows]

    logger.info("Running: %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return {"error": "deepline enrich timed out after 5 minutes"}
    except FileNotFoundError:
        return {"error": "deepline CLI not found — install with: npm i -g deepline"}

    if result.returncode != 0:
        return {
            "error": f"deepline enrich failed (exit {result.returncode})",
            "stderr": result.stderr[-500:] if result.stderr else "",
        }

    # Parse summary from stdout
    summary: dict = {}
    try:
        summary = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        pass

    # Read output CSV summary (never read full CSV into context)
    csv_stats: dict = {}
    if output_path.exists():
        try:
            show_result = subprocess.run(
                ["deepline", "csv", "show", "--csv", str(output_path), "--summary"],
                capture_output=True, text=True, timeout=30,
            )
            if show_result.returncode == 0:
                try:
                    csv_stats = json.loads(show_result.stdout)
                except (json.JSONDecodeError, ValueError):
                    csv_stats = {"summary": show_result.stdout[:500]}
        except Exception as e:
            logger.debug("csv show failed: %s", e)

    return {
        "output_csv": str(output_path),
        "rows_processed": "all" if full_run else rows,
        "columns_enriched": len(columns),
        "summary": summary,
        "csv_stats": csv_stats,
        "pilot_done": not full_run,
        "next_step": (
            "Pilot complete. Review results above, then call batch_enrich again "
            "with full_run=True to process all rows." if not full_run else None
        ),
    }


# ---------------------------------------------------------------------------
# Durable prospect list jobs
# ---------------------------------------------------------------------------


def build_prospect_list_job(
    criteria: str,
    target_count: int = 25,
    persona: Optional[str] = None,
    discovery_tool_id: Optional[str] = None,
    discovery_payload: Optional[dict[str, Any]] = None,
    seed_rows: Optional[list[dict[str, Any]]] = None,
    seed_csv_path: Optional[str] = None,
    enrichment_columns: Optional[list[dict[str, Any]]] = None,
    output_dir: Optional[str] = None,
    run_full: bool = False,
) -> dict:
    """
    Run a durable prospect/list-building job instead of freeform research.

    Use this for bulk prospecting or account-list tasks (5+ requested rows). The
    job follows the Deepline docs pattern:
    1. build an auditable seed CSV,
    2. run a deepline enrich --rows 0:1 pilot for row-level people/research work,
    3. stop for review by default,
    4. optionally run the full enrichment after explicit approval.

    Args:
        criteria: Natural-language ICP/list criteria.
        target_count: Number of final complete rows requested.
        persona: Optional contact/persona target to find at each seed company.
        discovery_tool_id: Optional Deepline search tool to run for seed rows
            (for example crustdata_companydb_search or dropleads_search_people).
        discovery_payload: Payload for discovery_tool_id.
        seed_rows: Optional pre-discovered company/account rows. If omitted, the
            tool runs discovery_tool_id, or asks Exa research for a JSON company
            seed list as a generic fallback.
        seed_csv_path: Existing seed CSV from a previous pilot. Use this with
            run_full=True after approval to avoid rediscovery.
        enrichment_columns: Optional explicit Deepline enrich column specs. If
            omitted and persona is provided, uses exa_people_search per company.
        output_dir: Optional artifact directory. Defaults to ~/deepline/data/<slug>/.
        run_full: False by default. Set True only after the pilot is approved.

    Returns:
        Job metadata, seed CSV path, pilot/full output paths, validation stats,
        and the recommended next step.
    """
    try:
        target_count = int(target_count or 25)
    except (TypeError, ValueError):
        target_count = 25
    target_count = max(1, min(target_count, 1000))
    seed_target = max(target_count, int(target_count * 1.4 + 0.999))
    slug = _slugify(criteria)
    seed_csv = Path(seed_csv_path).expanduser() if seed_csv_path else None
    if output_dir:
        work = Path(output_dir).expanduser()
    elif seed_csv:
        work = seed_csv.parent
    else:
        work = _work_dir(slug)
    work.mkdir(parents=True, exist_ok=True)

    plan = {
        "criteria": criteria,
        "target_count": target_count,
        "seed_target": seed_target,
        "persona": persona,
        "discovery_tool_id": discovery_tool_id or "exa_research",
        "seed_csv_path": str(seed_csv) if seed_csv else None,
        "phases": [
            "discover seed companies/accounts",
            "write seed CSV",
            "pilot row-level enrichment with deepline enrich --rows 0:1",
            "review pilot output",
            "run full enrichment after approval",
            "validate final CSV and deliver artifacts",
        ],
    }
    plan_path = work / "prospect_job_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")

    discovery_raw: Any = None
    using_existing_seed_csv = seed_csv is not None
    if seed_csv:
        if not seed_csv.exists():
            return {
                "job_status": "missing_seed_csv",
                "plan_path": str(plan_path),
                "seed_csv": str(seed_csv),
                "error": f"Seed CSV not found: {seed_csv}",
                "next_step": "Pass a valid seed_csv_path from the approved pilot job.",
            }
        seed_rows = _read_csv_rows(seed_csv)
    elif seed_rows is None:
        try:
            if discovery_tool_id:
                discovery_raw = deepline_execute(discovery_tool_id, discovery_payload or {})
            else:
                discovery_raw = deepline_execute("exa_research", {
                    "instructions": (
                        f"Find {seed_target} real companies/accounts matching this GTM ICP: {criteria}. "
                        "Return JSON only as an array of objects. Each object should include "
                        "company_name, domain, description, industry, location, headcount, and evidence_url "
                        "when available. Do not include markdown."
                    ),
                    "model": "exa-research-fast",
                })
        except Exception as e:
            return {
                "job_status": "discovery_error",
                "plan_path": str(plan_path),
                "error": f"Seed discovery failed: {e}",
                "next_step": "Inspect the criteria or pass seed_rows from a known provider/search result.",
            }
        seed_rows = _coerce_seed_rows(discovery_raw)
    else:
        seed_rows = _coerce_seed_rows(seed_rows)

    if not seed_rows:
        raw_path = work / "seed_discovery_raw.json"
        raw_path.write_text(json.dumps(discovery_raw, indent=2, default=str) + "\n")
        return {
            "job_status": "needs_seed_rows",
            "plan_path": str(plan_path),
            "raw_discovery_path": str(raw_path),
            "error": (
                "Could not parse seed rows from discovery output. Try a more structured "
                "provider search or pass seed_rows from a known source."
            ),
            "next_step": "Create/pass seed_rows, then rerun build_prospect_list_job.",
        }

    if not using_existing_seed_csv:
        seed_rows = seed_rows[:seed_target]
    if persona:
        for row in seed_rows:
            row.setdefault("persona", persona)

    if not seed_csv:
        seed_csv = work / "seed_companies.csv"
        _write_csv(
            seed_csv,
            seed_rows,
            fieldnames=[
                "company_name",
                "domain",
                "persona",
                "description",
                "industry",
                "location",
                "headcount",
                "evidence_url",
            ],
        )
    seed_summary = _csv_summary(seed_csv)

    if not persona and not enrichment_columns:
        return {
            "job_status": "seed_ready",
            "plan_path": str(plan_path),
            "seed_csv": str(seed_csv),
            "seed_summary": seed_summary,
            "target_count": target_count,
            "seed_target": seed_target,
            "next_step": (
                "Review the seed CSV, then provide persona or enrichment_columns "
                "to run row-level enrichment."
            ),
        }

    columns = enrichment_columns or [
        {
            "alias": "contacts",
            "tool": "exa_people_search",
            "payload": {
                "query": f"{persona} at {{{{company_name}}}}",
                "numResults": 3,
            },
        }
    ]

    if run_full and using_existing_seed_csv:
        pilot = {
            "skipped": True,
            "reason": "run_full=True with an existing seed_csv_path; using the approved seed CSV.",
        }
    else:
        pilot = batch_enrich(
            input_csv=str(seed_csv),
            columns=columns,
            output_dir=str(work / "pilot"),
            rows="0:1",
            full_run=False,
        )
    result: dict[str, Any] = {
        "job_status": "pilot_ready",
        "plan_path": str(plan_path),
        "seed_csv": str(seed_csv),
        "seed_summary": seed_summary,
        "pilot": pilot,
        "target_count": target_count,
        "seed_target": seed_target,
        "next_step": (
            "Review the pilot output. If it matches the desired shape, call this tool again "
            f"with seed_csv_path={str(seed_csv)!r} and run_full=True after explicit approval."
        ),
    }

    if isinstance(pilot, dict) and pilot.get("error"):
        result.update({
            "job_status": "pilot_error",
            "next_step": "Fix the pilot error before running the full enrichment.",
        })
        return result

    if run_full and not using_existing_seed_csv:
        result.update({
            "job_status": "approval_required",
            "next_step": (
                "Pilot complete. Review the pilot output, then rerun with "
                f"seed_csv_path={str(seed_csv)!r} and run_full=True after explicit approval."
            ),
        })
        return result

    if not run_full:
        return result

    full = batch_enrich(
        input_csv=str(seed_csv),
        columns=columns,
        output_dir=str(work),
        full_run=True,
    )
    if full.get("error"):
        result.update({
            "job_status": "full_error",
            "full_run": full,
            "output_csv": None,
            "output_summary": {},
            "next_step": "Fix the full-run error, then rerun with the same seed_csv_path.",
        })
        return result

    output_value = full.get("output_csv")
    output_csv = Path(output_value) if output_value else None
    result.update({
        "job_status": "complete",
        "full_run": full,
        "output_csv": str(output_csv) if output_csv else None,
        "output_summary": _csv_summary(output_csv) if output_csv else {},
        "next_step": "Deliver the output CSV and summarize coverage, gaps, and sources.",
    })
    return result


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


def verify_email(email: str) -> dict:
    """
    Verify an email address before sending outreach.

    Checks deliverability, MX records, and SMTP validity.
    Returns: {"email": str, "valid": bool, "status": str, "safe_to_send": bool}
    """
    try:
        result = deepline_execute("leadmagic_email_validation", {"email": email})
        # LeadMagic returns "email_status" field (not "status")
        status = result.get("email_status", result.get("status", "unknown"))
        if status != "unknown":
            return {
                "provider": "leadmagic",
                "email": email,
                "valid": status == "valid",
                "status": status,
                "safe_to_send": status == "valid",
                "mx_provider": result.get("mx_provider"),
                "company_name": result.get("company_name"),
            }
        # Fall through to ZeroBounce if LeadMagic returns unknown
    except Exception as e:
        logger.debug("leadmagic_email_validation failed for verify_email: %s", e)

    result = deepline_execute("zerobounce_batch_validate", {"email_batch": [{"email_address": email}]})
    items = result.get("email_batch", [])
    if items:
        item = items[0]
        status = item.get("status", "unknown")
        sub_status = item.get("sub_status", "")
        return {
            "provider": "zerobounce",
            "email": email,
            "valid": status == "valid",
            "status": status,
            "sub_status": sub_status,
            "safe_to_send": status == "valid" and sub_status not in ("disposable", "role_based"),
        }
    return {"email": email, "valid": False, "status": "unknown", "safe_to_send": False}


# ---------------------------------------------------------------------------
# LinkedIn URL lookup
# ---------------------------------------------------------------------------


def find_linkedin(
    first_name: str,
    last_name: str,
    company_name: Optional[str] = None,
    company_domain: Optional[str] = None,
) -> dict:
    """
    Find a person's LinkedIn profile URL given their name and company.

    Waterfall: Deepline Native Prospector (if domain known) → Exa web research.
    Returns: {"linkedin_url": str, "confidence": str}
    """
    # Deepline Native enrich_contact — returns linkedin_url for a known name + domain
    # enrich_contact is the correct single-contact tool; prospector requires a title filter
    if company_domain:
        try:
            result = deepline_execute("deepline_native_enrich_contact", {
                "first_name": first_name,
                "last_name": last_name,
                "domain": company_domain,
            })
            linkedin = (
                result.get("linkedin_url")
                or result.get("linkedin")
                or (result.get("data") or {}).get("linkedin_url")
                or (result.get("data") or {}).get("linkedin")
            )
            if linkedin:
                return {
                    "linkedin_url": linkedin,
                    "confidence": "high",
                    "provider": "deepline_native_enrich_contact",
                }
        except Exception as e:
            logger.debug("deepline_native_enrich_contact failed for find_linkedin: %s", e)

    # Exa web research fallback — finds LinkedIn profiles via live web search
    try:
        company_hint = f" at {company_name or company_domain}" if (company_name or company_domain) else ""
        result = deepline_execute("exa_research", {
            "instructions": f"Find the LinkedIn profile URL for {first_name} {last_name}{company_hint}. Return only the linkedin.com/in/... URL.",
            "model": "exa-research-fast",
        })
        data = result.get("data") or result
        summary = str(data.get("output", ""))
        # Extract linkedin.com/in/ URL from the response
        import re
        match = re.search(r"https?://(?:www\.)?linkedin\.com/in/[\w\-]+/?", summary)
        if match:
            return {"linkedin_url": match.group(0), "confidence": "medium", "provider": "exa_research"}
    except Exception as e:
        logger.debug("exa_research failed for find_linkedin: %s", e)

    return {"linkedin_url": "", "confidence": "none"}


# ---------------------------------------------------------------------------
# Company list building
# ---------------------------------------------------------------------------


def search_companies(
    industry: Optional[str] = None,
    location: Optional[str] = None,
    headcount_min: Optional[int] = None,
    headcount_max: Optional[int] = None,
    keywords: Optional[str] = None,
    limit: int = 25,
) -> dict:
    """
    Build a list of companies matching ICP criteria.

    Uses Exa web research to find companies by industry, location, headcount range, or keyword.
    Use this to build target account lists before finding contacts.

    headcount_min / headcount_max: integer employee counts (e.g. 200, 500).
    Returns a list of companies with name, domain, headcount, industry, and description.
    """
    criteria_parts = []
    if industry:
        criteria_parts.append(f"industry: {industry}")
    if location:
        criteria_parts.append(f"location: {location}")
    if headcount_min and headcount_max:
        criteria_parts.append(f"{headcount_min}–{headcount_max} employees")
    elif headcount_min:
        criteria_parts.append(f"at least {headcount_min} employees")
    elif headcount_max:
        criteria_parts.append(f"up to {headcount_max} employees")
    if keywords:
        criteria_parts.append(f"keywords: {keywords}")

    criteria = ", ".join(criteria_parts) or "general B2B companies"

    try:
        result = deepline_execute("exa_research", {
            "instructions": (
                f"Find {limit} real companies matching these criteria: {criteria}. "
                "For each company return: company name, website domain, estimated headcount, industry, "
                "one-sentence description, and HQ city. Format as a structured list."
            ),
            "model": "exa-research-fast",
        })
        data = result.get("data") or result
        summary = data.get("output", "")
        return {
            "provider": "exa_research",
            "criteria": criteria,
            "count": limit,
            "companies": summary,
        }
    except Exception as e:
        logger.debug("exa_research failed for search_companies: %s", e)
        return {"error": f"Company search failed: {e}", "criteria": criteria}
