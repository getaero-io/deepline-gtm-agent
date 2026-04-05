"""
Deepline operations exposed as Deep Agents-compatible tool functions.

Each function follows the Deep Agents convention:
- Plain Python function with a clear docstring
- Type-annotated parameters (auto-generate the tool schema)
- Returns a dict or str that the agent can reason about
"""

import logging
import re as _re_module
from typing import Any, Optional
from deepline_gtm_agent.deepline import deepline_execute
from deepline_gtm_agent.orgchart import (
    slugify,
    classify_seniority,
    SENIORITY_LABELS,
    extract_team_from_title,
    extract_teams_from_jobs,
    assign_team,
    build_hierarchy,
)

logger = logging.getLogger(__name__)


def _normalize_linkedin_url(url: str) -> str:
    """Ensure a LinkedIn URL is fully qualified with https://www.linkedin.com prefix."""
    if not url:
        return url
    url = url.strip().rstrip("/")
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

    # Hunter email finder — best for domain + name lookup
    if company_domain and first_name and last_name:
        try:
            result = deepline_execute("hunter_email_finder", {
                "domain": company_domain,
                "first_name": first_name,
                "last_name": last_name,
            })
            if result.get("email"):
                return {
                    "provider": "hunter",
                    "email": result.get("email"),
                    "name": f"{first_name} {last_name}".strip(),
                    "company": company_name or company_domain,
                    "linkedin_url": linkedin_url,
                }
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
    # Note: Deepline "play" tools (name_and_company_to_email_waterfall, etc.) are
    # CLI-only and cannot be called via the HTTP execute API.
    # We implement the same sequence manually here.

    providers_tried: list[str] = []

    # 1. Dropleads email finder — free, fast
    if first_name and last_name:
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


# ---------------------------------------------------------------------------
# Org chart builder
# ---------------------------------------------------------------------------


def build_org_chart(
    linkedin_url: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    company_domain: Optional[str] = None,
    company_name: Optional[str] = None,
) -> dict:
    """
    Build an org chart around a target person at a company.

    Finds employees via Apollo, Dropleads, and Deepline Native (free) to
    maximize coverage. Classifies seniority, infers team membership from
    job listings, and builds a hierarchy with manager, peers, and direct reports.

    Provide at least one of: linkedin_url, or (first_name + last_name + company).
    Returns: people dict, hierarchy graph, and summary with manager/peers/reports.
    """
    target_name = None
    target_title = None

    if not any([linkedin_url, (first_name and last_name)]):
        return {"error": "Provide linkedin_url, or first_name + last_name (+ company)."}

    # -----------------------------------------------------------------
    # Step 1: Resolve target identity
    # -----------------------------------------------------------------
    if linkedin_url:
        linkedin_url = _normalize_linkedin_url(linkedin_url)
        try:
            profile = deepline_execute("leadmagic_profile_search", {
                "url": linkedin_url,
            })
            first_name = first_name or profile.get("first_name", "")
            last_name = last_name or profile.get("last_name", "")
            target_title = profile.get("current_position_title", "")
            company_name = company_name or profile.get("company_name", "")
            company_domain = company_domain or profile.get("company_website", "")
        except Exception as e:
            logger.debug("leadmagic_profile_search failed: %s", e)

    if not company_domain and company_name:
        try:
            exa_result = deepline_execute("exa_search", {
                "query": f"{company_name} official website",
                "numResults": 1,
            })
            results = exa_result.get("results", [])
            if results:
                url = results[0].get("url", "")
                domain_match = _re_module.search(
                    r"https?://(?:www\.)?([^/]+)", url
                )
                if domain_match:
                    company_domain = domain_match.group(1)
        except Exception as e:
            logger.debug("exa_search for domain resolution failed: %s", e)

    if not company_domain and not company_name:
        return {"error": "Could not determine company. Provide company_domain or company_name."}

    target_name = f"{first_name or ''} {last_name or ''}".strip()

    # -----------------------------------------------------------------
    # Step 2: Find ALL employees (wide net)
    # -----------------------------------------------------------------
    raw_people: list[dict] = []

    # Apollo search - 4 seniority tiers
    apollo_tiers = [
        (["owner", "founder", "c_suite", "vp"], 50),
        (["head", "director"], 50),
        (["manager"], 50),
        (["senior", "entry"], 30),
    ]
    for seniorities, per_page in apollo_tiers:
        try:
            payload = {
                "person_seniorities": seniorities,
                "per_page": per_page,
            }
            if company_domain:
                payload["q_organization_domains"] = company_domain
            elif company_name:
                payload["q_organization_name"] = company_name
            result = deepline_execute("apollo_search_people", payload)
            people_list = result.get("people", [])
            for p in people_list:
                raw_people.append({
                    "name": p.get("name", ""),
                    "title": p.get("title", ""),
                    "linkedin_url": p.get("linkedin_url", ""),
                    "city": p.get("city", ""),
                    "state": p.get("state", ""),
                    "country": p.get("country", ""),
                    "email": p.get("email", ""),
                    "departments": p.get("departments", []),
                    "source": "apollo",
                })
        except Exception as e:
            logger.debug("apollo_search_people (seniorities=%s) failed: %s", seniorities, e)

    # Dropleads supplementary source
    if company_domain:
        try:
            dl_result = deepline_execute("dropleads_search_people", {
                "filters": {"companyDomains": [company_domain]},
                "pagination": {"page": 1, "limit": 100},
            })
            leads = (dl_result.get("data") or dl_result).get("leads", dl_result.get("leads", []))
            for lead in leads:
                raw_people.append({
                    "name": lead.get("fullName", ""),
                    "title": lead.get("title", ""),
                    "linkedin_url": lead.get("linkedinUrl", ""),
                    "city": "",
                    "state": "",
                    "country": "",
                    "email": lead.get("email", ""),
                    "departments": [],
                    "location": lead.get("location", ""),
                    "source": "dropleads",
                })
        except Exception as e:
            logger.debug("dropleads_search_people failed: %s", e)

    # Deepline Native search (free) - additional coverage on top of Apollo + Dropleads
    dn_title_tiers = [
        "CEO OR CTO OR CFO OR COO OR CMO OR CRO OR Founder OR Co-Founder",
        "VP OR Vice President OR SVP",
        "Head OR Director OR Senior Director",
        "Manager OR Senior Manager",
    ]
    for title_filter in dn_title_tiers:
        try:
            dn_payload: dict[str, Any] = {"title_filters": [{"name": "tier", "filter": title_filter}]}
            if company_domain:
                dn_payload["domain"] = company_domain
            elif company_name:
                dn_payload["company_name"] = company_name
            else:
                continue
            dn_result = deepline_execute("deepline_native_search_contact", dn_payload)
            # deepline_execute unwraps result.data -> {status, output: {persons: [...]}}
            dn_output = dn_result.get("output", dn_result) if isinstance(dn_result, dict) else {}
            dn_persons = dn_output.get("persons", dn_output.get("contacts", dn_output.get("results", [])))
            if isinstance(dn_persons, list):
                for p in dn_persons:
                    raw_people.append({
                        "name": p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                        "title": p.get("title", ""),
                        "linkedin_url": p.get("linkedin_url") or p.get("linkedin", ""),
                        "city": p.get("city", ""),
                        "state": p.get("state", ""),
                        "country": p.get("country", ""),
                        "email": p.get("professional_email") or p.get("email", ""),
                        "departments": [p["department"]] if p.get("department") else [],
                        "source": "deepline_native",
                    })
        except Exception as e:
            logger.debug("deepline_native_search_contact (filter=%s) failed: %s", title_filter, e)

    # Deduplicate by slugified name, merge sources
    seen: dict[str, dict] = {}
    for person in raw_people:
        name = person.get("name", "").strip()
        if not name:
            continue
        slug = slugify(name)
        if not slug:
            continue
        if slug in seen:
            # Merge: add source, prefer non-empty fields
            existing = seen[slug]
            if person["source"] not in existing["sources"]:
                existing["sources"].append(person["source"])
            for field in ("title", "linkedin_url", "email", "city", "state", "country"):
                if not existing.get(field) and person.get(field):
                    existing[field] = person[field]
            if person.get("departments"):
                existing.setdefault("departments", [])
                for d in person["departments"]:
                    if d not in existing["departments"]:
                        existing["departments"].append(d)
        else:
            seen[slug] = {
                "slug": slug,
                "name": name,
                "title": person.get("title", ""),
                "linkedin_url": person.get("linkedin_url", ""),
                "city": person.get("city", ""),
                "state": person.get("state", ""),
                "country": person.get("country", ""),
                "email": person.get("email", ""),
                "departments": list(person.get("departments", [])),
                "sources": [person["source"]],
            }

    # Classify seniority and extract team from title
    for slug, person in seen.items():
        person["seniority"] = classify_seniority(person["title"])
        person["seniority_label"] = SENIORITY_LABELS.get(person["seniority"], "")
        person["team"] = extract_team_from_title(person["title"])
        if not person["team"] and person.get("departments"):
            person["team"] = person["departments"][0]

    # Ensure target person is in the list
    target_slug = slugify(target_name) if target_name else ""
    if target_slug and target_slug not in seen:
        seen[target_slug] = {
            "slug": target_slug,
            "name": target_name,
            "title": target_title or "",
            "linkedin_url": linkedin_url or "",
            "city": "",
            "state": "",
            "country": "",
            "email": "",
            "departments": [],
            "sources": ["input"],
            "seniority": classify_seniority(target_title or ""),
            "seniority_label": SENIORITY_LABELS.get(classify_seniority(target_title or ""), ""),
            "team": extract_team_from_title(target_title or ""),
        }

    # -----------------------------------------------------------------
    # Step 3: Fetch job listings and assign teams
    # -----------------------------------------------------------------
    known_teams: set[str] = set()
    if company_domain:
        try:
            jobs_result = deepline_execute("crustdata_job_listings", {
                "companyDomains": company_domain,
                "limit": 100,
            })
            # Crustdata returns {listings: [{title, category, ...}]} or a flat list
            job_listings = jobs_result.get("listings", jobs_result.get("data", []))
            if isinstance(job_listings, list):
                # Normalize: Crustdata uses "category" not "department"
                normalized = []
                for jl in job_listings:
                    normalized.append({
                        "title": jl.get("title", ""),
                        "department": jl.get("category") or jl.get("department", ""),
                        "team": jl.get("team", ""),
                    })
                known_teams = extract_teams_from_jobs(normalized)
        except Exception as e:
            logger.debug("crustdata_job_listings failed: %s", e)

    # Assign teams to people who don't have one
    for slug, person in seen.items():
        if not person.get("team"):
            dept = person["departments"][0] if person.get("departments") else ""
            person["team"] = assign_team(person["title"], known_teams, department=dept)

    # -----------------------------------------------------------------
    # Step 4: Build hierarchy
    # -----------------------------------------------------------------
    people_for_hierarchy = list(seen.values())

    if not target_slug:
        return {"error": "Could not determine target person slug."}

    hierarchy = build_hierarchy(target_slug, people_for_hierarchy)

    # Build people dict (only included people from the hierarchy)
    included_slugs: set[str] = set()
    included_slugs.add(hierarchy.get("root", ""))
    included_slugs.add(hierarchy.get("target", ""))
    for parent, children in hierarchy.get("edges", {}).items():
        included_slugs.add(parent)
        for child in children:
            included_slugs.add(child)
    included_slugs.discard("")

    def _confidence(sources: list[str]) -> str:
        n = len(sources)
        if n >= 3:
            return "high"
        if n >= 2:
            return "medium"
        return "low"

    people_dict: dict[str, dict] = {}
    for slug in included_slugs:
        person = seen.get(slug)
        if not person:
            continue
        li = person.get("linkedin_url", "")
        if li:
            li = _normalize_linkedin_url(li)
        location_parts = [
            p for p in [person.get("city"), person.get("state"), person.get("country")] if p
        ]
        people_dict[slug] = {
            "name": person["name"],
            "title": person.get("title", ""),
            "seniority": person.get("seniority", "ic"),
            "seniority_label": person.get("seniority_label", ""),
            "team": person.get("team", ""),
            "location": ", ".join(location_parts),
            "linkedin": li,
            "email": person.get("email", ""),
            "sources": person.get("sources", []),
            "confidence": _confidence(person.get("sources", [])),
        }

    # -----------------------------------------------------------------
    # Step 5: Build summary
    # -----------------------------------------------------------------
    edges = hierarchy.get("edges", {})
    target_person = seen.get(target_slug, {})

    # Find manager: who has target as a child?
    manager_slug = None
    for parent, children in edges.items():
        if target_slug in children:
            manager_slug = parent
            break

    manager_name = None
    manager_title = None
    if manager_slug and manager_slug in seen:
        manager_name = seen[manager_slug]["name"]
        manager_title = seen[manager_slug].get("title", "")

    # Find peers: siblings under the same manager
    peers: list[str] = []
    if manager_slug and manager_slug in edges:
        for child in edges[manager_slug]:
            if child != target_slug and child in seen:
                peers.append(seen[child]["name"])

    # Find direct reports: children of target
    direct_reports: list[str] = []
    if target_slug in edges:
        for child in edges[target_slug]:
            if child in seen:
                direct_reports.append(seen[child]["name"])

    summary = {
        "target": target_person.get("name", target_name),
        "target_title": target_person.get("title", target_title or ""),
        "manager": manager_name,
        "manager_title": manager_title,
        "peers": peers[:10],
        "direct_reports": direct_reports[:10],
        "total_people": len(people_dict),
        "company": company_name or "",
        "domain": company_domain or "",
    }

    return {
        "people": people_dict,
        "hierarchy": hierarchy,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Waterfall.io integration
# ---------------------------------------------------------------------------


def waterfall_prospect(
    domain: str,
    title_filter: str = "",
    limit: int = 25,
    include_phones: bool = False,
    location_countries: Optional[list[str]] = None,
) -> dict:
    """
    Find contacts at a company using Waterfall.io's Prospector.

    Waterfall aggregates 30+ data vendors for high coverage.
    Async: launches a job and polls until results are ready.

    Args:
        domain: Company domain (e.g. "stripe.com")
        title_filter: Boolean title filter (e.g. "VP Sales OR Director Marketing")
        limit: Max results (1-500, default 25)
        include_phones: Also enrich phone numbers
        location_countries: Filter by country codes

    Returns: {company, persons: [{first_name, last_name, title, email, linkedin_url, ...}]}
    """
    from deepline_gtm_agent.waterfall_client import waterfall_async_job

    payload = {"domain": domain, "limit": limit, "include_phones": include_phones, "verified_only": True}
    if title_filter:
        payload["title_filter"] = title_filter
    if location_countries:
        payload["location_countries"] = location_countries

    result = waterfall_async_job("/v1/prospector", payload)
    output = result.get("output", {})
    return {
        "provider": "waterfall",
        "status": result.get("status"),
        "company": output.get("company", {}),
        "persons": output.get("persons", []),
        "count": len(output.get("persons", [])),
    }


def waterfall_enrich_contact(
    linkedin: Optional[str] = None,
    email: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    full_name: Optional[str] = None,
    domain: Optional[str] = None,
    include_phones: bool = False,
) -> dict:
    """
    Enrich a contact using Waterfall.io's 30+ data vendors.

    Provide one of: linkedin URL, email, or name + domain.
    Returns enriched person with email, phone, title, company, experience history.
    """
    from deepline_gtm_agent.waterfall_client import waterfall_async_job

    payload = {"include_phones": include_phones}
    if linkedin:
        payload["linkedin"] = linkedin
    elif email:
        payload["email"] = email
    elif full_name and domain:
        payload["full_name"] = full_name
        payload["domain"] = domain
    elif first_name and last_name and domain:
        payload["first_name"] = first_name
        payload["last_name"] = last_name
        payload["domain"] = domain
    else:
        return {"error": "Provide linkedin, email, or name + domain."}

    result = waterfall_async_job("/v1/enrichment/contact", payload)
    person = result.get("output", {}).get("person", {})
    return {"provider": "waterfall", "status": result.get("status"), **person}


def waterfall_enrich_phone(
    linkedin: Optional[str] = None,
    email: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    domain: Optional[str] = None,
) -> dict:
    """
    Get phone numbers for a contact using Waterfall.io.

    Returns mobile and direct dial numbers. Provide linkedin, email, or name + domain.
    """
    from deepline_gtm_agent.waterfall_client import waterfall_async_job

    payload = {}
    if linkedin:
        payload["linkedin"] = linkedin
    elif email:
        payload["email"] = email
    elif first_name and last_name and domain:
        payload["first_name"] = first_name
        payload["last_name"] = last_name
        payload["domain"] = domain
    else:
        return {"error": "Provide linkedin, email, or name + domain."}

    result = waterfall_async_job("/v1/enrichment/phone", payload)
    person = result.get("output", {}).get("person", {})
    return {"provider": "waterfall_phone", "status": result.get("status"), "mobile_phone": person.get("mobile_phone"), "phone_numbers": person.get("phone_numbers"), **person}


def waterfall_enrich_company(
    domain: Optional[str] = None,
    linkedin: Optional[str] = None,
    name: Optional[str] = None,
) -> dict:
    """
    Enrich company data using Waterfall.io.

    Returns company profile with domain, industry, size, funding, LinkedIn data.
    Provide one of: domain, LinkedIn URL, or company name.
    """
    from deepline_gtm_agent.waterfall_client import waterfall_async_job

    payload = {}
    if domain:
        payload["domain"] = domain
    elif linkedin:
        payload["linkedin"] = linkedin
    elif name:
        payload["name"] = name
    else:
        return {"error": "Provide domain, linkedin, or name."}

    result = waterfall_async_job("/v1/enrichment/company", payload)
    company = result.get("output", {}).get("company", {})
    return {"provider": "waterfall_company", "status": result.get("status"), **company}


def waterfall_search_contacts(
    domain: Optional[str] = None,
    company_name: Optional[str] = None,
    title_filters: Optional[list[str]] = None,
    seniorities: Optional[list[str]] = None,
    departments: Optional[list[str]] = None,
    location_countries: Optional[list[str]] = None,
    page_size: int = 25,
    page_number: int = 1,
) -> dict:
    """
    Search for contacts using Waterfall.io's database.

    Synchronous - returns results inline. Supports filtering by title, seniority,
    department, location, and company.

    Returns: {persons: [{first_name, last_name, title, email, linkedin_url, ...}]}
    """
    from deepline_gtm_agent.waterfall_client import waterfall_request

    payload = {"page_size": page_size, "page_number": page_number}
    if domain:
        payload["domain"] = domain
    if company_name:
        payload["company_name"] = company_name
    if title_filters:
        payload["title_filters"] = title_filters
    if seniorities:
        payload["seniorities"] = seniorities
    if departments:
        payload["departments"] = departments
    if location_countries:
        payload["location_countries"] = location_countries

    result = waterfall_request("POST", "/v1/search/contact", payload=payload)
    output = result.get("output", {})
    return {
        "provider": "waterfall_search",
        "status": result.get("status"),
        "persons": output.get("persons", []),
        "count": len(output.get("persons", [])),
    }


def waterfall_search_companies(
    industries: Optional[list[str]] = None,
    location_countries: Optional[list[str]] = None,
    sizes: Optional[list[str]] = None,
    page_size: int = 25,
    page_number: int = 1,
) -> dict:
    """
    Search for companies using Waterfall.io.

    Filter by industry, location, and employee size. Returns enriched company profiles.
    """
    from deepline_gtm_agent.waterfall_client import waterfall_request

    payload = {"page_size": page_size, "page_number": page_number}
    if industries:
        payload["industries"] = industries
    if location_countries:
        payload["location_countries"] = location_countries
    if sizes:
        payload["sizes"] = sizes

    if not any([industries, location_countries, sizes]):
        return {"error": "Provide at least one of: industries, location_countries, sizes."}

    result = waterfall_request("POST", "/v1/search/company", payload=payload)
    output = result.get("output", {})
    return {
        "provider": "waterfall_search",
        "status": result.get("status"),
        "companies": output.get("companies", []),
        "count": len(output.get("companies", [])),
    }


def waterfall_job_change(
    company_domain: Optional[str] = None,
    contact_linkedin: Optional[str] = None,
    professional_email: Optional[str] = None,
    contact_full_name: Optional[str] = None,
) -> dict:
    """
    Check if a contact has changed jobs using Waterfall.io.

    Detects: left, moved (new company), promoted, no_change, or unknown.
    Useful for keeping CRM data fresh and detecting buying signals.

    Returns: {job_change_status, person (if found at new company)}
    """
    from deepline_gtm_agent.waterfall_client import waterfall_async_job

    payload = {}
    if company_domain:
        payload["company_domain"] = company_domain
    if contact_linkedin:
        payload["contact_linkedin"] = contact_linkedin
    if professional_email:
        payload["professional_email"] = professional_email
    if contact_full_name:
        payload["contact_full_name"] = contact_full_name

    if not payload:
        return {"error": "Provide company_domain + contact identifier."}

    result = waterfall_async_job("/v1/job-change", payload)
    output = result.get("output", {})
    return {
        "provider": "waterfall_job_change",
        "status": result.get("status"),
        "job_change_status": output.get("job_change_status"),
        "person": output.get("person", {}),
    }


def waterfall_verify_email(email: str) -> dict:
    """
    Verify an email address using Waterfall.io.

    Returns: {email, email_status: "valid"|"invalid"|"risky"|"unknown", smtp_provider, mx_records}
    """
    from deepline_gtm_agent.waterfall_client import waterfall_request

    result = waterfall_request("POST", "/v1/verify-email", payload={"email": email})
    email_data = result.get("output", {}).get("email", {})
    return {
        "provider": "waterfall_verify",
        "email": email,
        "email_status": email_data.get("email_status"),
        "valid": email_data.get("email_status") == "valid",
        "safe_to_send": email_data.get("email_status") in ("valid",),
        "smtp_provider": email_data.get("smtp_provider"),
        "mx_records": email_data.get("mx_records", []),
    }
