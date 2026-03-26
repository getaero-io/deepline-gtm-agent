"""
Deepline operations exposed as Deep Agents-compatible tool functions.

Each function follows the Deep Agents convention:
- Plain Python function with a clear docstring
- Type-annotated parameters (auto-generate the tool schema)
- Returns a dict or str that the agent can reason about

The Deep Agents framework picks these up automatically when passed to
`create_deep_agent(tools=[...])`.
"""

from typing import Optional
from deepline_gtm_agent.deepline import deepline_execute


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
    Enrich a person's contact data using Deepline's waterfall enrichment.

    Looks up work email, phone, job title, and LinkedIn profile across
    multiple providers (Apollo, Crustdata, PeopleDataLabs, ContactOut, Wiza).
    At least one of linkedin_url, email, or (first_name + last_name + company)
    must be provided.

    Returns a dict with fields: email, phone, linkedin_url, title, company,
    location, and raw provider results.
    """
    if not any([linkedin_url, email, (first_name and last_name)]):
        return {
            "error": "Provide linkedin_url, email, or first_name + last_name to enrich a person."
        }

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

    # Try ContactOut first (highest email quality), fall back to Apollo
    try:
        result = deepline_execute("contactout_enrich_person", payload)
        if result.get("emails") or result.get("work_email"):
            return {"provider": "contactout", **result}
    except Exception:
        pass

    try:
        result = deepline_execute("wiza_reveal_person", {
            **payload,
            "enrichment_level": "partial",
        })
        if result.get("email"):
            return {"provider": "wiza", **result}
    except Exception:
        pass

    # Final fallback: Apollo
    result = deepline_execute("apollo_people_enrichment", payload)
    return {"provider": "apollo", **result}


# ---------------------------------------------------------------------------
# Prospect search
# ---------------------------------------------------------------------------


def search_prospects(
    job_title: Optional[str] = None,
    job_level: Optional[str] = None,
    company_name: Optional[str] = None,
    company_domain: Optional[str] = None,
    person_location: Optional[str] = None,
    company_size: Optional[str] = None,
    company_industry: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """
    Search for prospects (people) matching criteria across Deepline providers.

    Use job_level values like: owner, founder, c_suite, vp, director, manager.
    Use company_size values like: 1-10, 11-50, 51-200, 201-500, 501-1000, 1001+.

    Returns a list of matching people with name, title, company, and LinkedIn URL.
    Caps results at `limit` (default 10, max 100).
    """
    filters: dict = {}
    if job_title:
        filters["job_title"] = job_title
    if job_level:
        filters["job_level"] = job_level
    if person_location:
        filters["person_location"] = person_location
    if company_size:
        filters["company_size"] = company_size
    if company_industry:
        filters["company_industry"] = company_industry

    # Wiza prospect search is free — use it for discovery
    try:
        result = deepline_execute("wiza_search_prospects", {"filters": filters})
        prospects = result.get("prospects", [])[:limit]
        if prospects:
            return {"provider": "wiza", "count": len(prospects), "prospects": prospects}
    except Exception:
        pass

    # Apollo people search as fallback
    apollo_payload: dict = {"limit": limit}
    if job_title:
        apollo_payload["person_titles"] = [job_title]
    if job_level:
        apollo_payload["person_seniorities"] = [job_level]
    if company_name:
        apollo_payload["organization_names"] = [company_name]
    if company_domain:
        apollo_payload["organization_domains"] = [company_domain]
    if person_location:
        apollo_payload["person_locations"] = [person_location]
    if company_size:
        apollo_payload["organization_num_employees_ranges"] = [company_size]

    result = deepline_execute("apollo_people_search", apollo_payload)
    people = result.get("people", [])[:limit]
    return {"provider": "apollo", "count": len(people), "prospects": people}


# ---------------------------------------------------------------------------
# Company research
# ---------------------------------------------------------------------------


def research_company(
    domain: Optional[str] = None,
    company_name: Optional[str] = None,
) -> dict:
    """
    Research a company: funding, tech stack, headcount, description, and ICP fit.

    Fetches firmographic data, recent news, and technology signals from
    Crustdata, BuiltWith, and Apollo. Useful for account-level scoring and
    personalization.

    Provide domain (e.g. "stripe.com") or company_name.
    Returns a dict with: description, industry, headcount, funding, tech_stack,
    location, linkedin_url, website.
    """
    if not domain and not company_name:
        return {"error": "Provide domain or company_name."}

    payload: dict = {}
    if domain:
        payload["domain"] = domain
    if company_name:
        payload["name"] = company_name

    # Apollo company enrichment is solid for firmographics
    try:
        result = deepline_execute("apollo_organization_enrichment", payload)
        org = result.get("organization", result)
        return {
            "provider": "apollo",
            "name": org.get("name"),
            "domain": org.get("primary_domain") or domain,
            "description": org.get("short_description"),
            "industry": org.get("industry"),
            "headcount": org.get("estimated_num_employees"),
            "funding": org.get("total_funding_printed"),
            "location": org.get("city"),
            "linkedin_url": org.get("linkedin_url"),
            "website": org.get("website_url"),
        }
    except Exception:
        pass

    # Crustdata for LinkedIn-signal-heavy data
    if domain or company_name:
        result = deepline_execute(
            "crustdata_company_search",
            {"filters": [{"filter_type": "COMPANY_WEBSITE_DOMAIN_EXACT_MATCH", "value": domain}]}
            if domain
            else {"filters": [{"filter_type": "COMPANY_NAME_FUZZY_MATCH", "value": company_name}]},
        )
        companies = result.get("companies", [])
        if companies:
            return {"provider": "crustdata", **companies[0]}

    return {"error": f"Could not find company data for {domain or company_name}"}


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


def verify_email(email: str) -> dict:
    """
    Verify an email address before sending outreach.

    Checks deliverability, MX records, and SMTP validity using LeadMagic
    (primary) with ZeroBounce fallback. Returns status, risk level, and
    whether the address is safe to send.

    Returns: {"email": str, "valid": bool, "status": str, "risk": str, "safe_to_send": bool}
    """
    try:
        result = deepline_execute("leadmagic_email_validation", {"email": email})
        status = result.get("status", "unknown")
        return {
            "provider": "leadmagic",
            "email": email,
            "valid": status == "valid",
            "status": status,
            "risk": result.get("mx_found") and "low" or "high",
            "safe_to_send": status == "valid",
            "raw": result,
        }
    except Exception:
        pass

    result = deepline_execute("zerobounce_email_validation", {"email": email})
    status = result.get("status", "unknown")
    sub_status = result.get("sub_status", "")
    return {
        "provider": "zerobounce",
        "email": email,
        "valid": status == "valid",
        "status": status,
        "sub_status": sub_status,
        "safe_to_send": status == "valid" and sub_status not in ("disposable", "role_based"),
        "raw": result,
    }


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

    Uses RocketReach and ContactOut for lookup. Returns the LinkedIn URL
    or an empty string if not found.

    Returns: {"linkedin_url": str, "confidence": str}
    """
    payload = {
        "name": f"{first_name} {last_name}",
        "current_employer": company_name or company_domain or "",
    }

    try:
        result = deepline_execute("rocketreach_lookup_person", payload)
        linkedin = result.get("linkedin_url", "")
        if linkedin:
            return {"provider": "rocketreach", "linkedin_url": linkedin, "confidence": "high"}
    except Exception:
        pass

    # ContactOut via Apollo people search for LinkedIn URL
    apollo_payload: dict = {
        "q_person_name": f"{first_name} {last_name}",
        "limit": 1,
    }
    if company_name:
        apollo_payload["organization_names"] = [company_name]

    try:
        result = deepline_execute("apollo_people_search", apollo_payload)
        people = result.get("people", [])
        if people and people[0].get("linkedin_url"):
            return {
                "provider": "apollo",
                "linkedin_url": people[0]["linkedin_url"],
                "confidence": "medium",
            }
    except Exception:
        pass

    return {"linkedin_url": "", "confidence": "none"}


# ---------------------------------------------------------------------------
# Company list building
# ---------------------------------------------------------------------------


def search_companies(
    industry: Optional[str] = None,
    location: Optional[str] = None,
    headcount_min: Optional[int] = None,
    headcount_max: Optional[int] = None,
    tech_stack: Optional[str] = None,
    keywords: Optional[str] = None,
    limit: int = 25,
) -> dict:
    """
    Build a list of companies matching ICP criteria.

    Searches Apollo and Crustdata for companies by industry, location,
    headcount range, tech stack, or keyword. Use this to build target
    account lists before finding contacts.

    headcount_min / headcount_max: integer employee counts.
    tech_stack: technology name (e.g. "Salesforce", "HubSpot").
    Returns a list of companies with name, domain, headcount, and description.
    """
    payload: dict = {"limit": limit}

    if industry:
        payload["organization_industry_tag_ids"] = [industry]
    if location:
        payload["organization_locations"] = [location]
    if headcount_min or headcount_max:
        lo = headcount_min or 1
        hi = headcount_max or 100000
        payload["organization_num_employees_ranges"] = [f"{lo},{hi}"]
    if keywords:
        payload["q_organization_keyword_tags"] = [keywords]

    try:
        result = deepline_execute("apollo_organization_search", payload)
        companies = result.get("organizations", [])[:limit]
        return {
            "provider": "apollo",
            "count": len(companies),
            "companies": [
                {
                    "name": c.get("name"),
                    "domain": c.get("primary_domain"),
                    "headcount": c.get("estimated_num_employees"),
                    "industry": c.get("industry"),
                    "description": c.get("short_description"),
                    "location": c.get("city"),
                }
                for c in companies
            ],
        }
    except Exception as e:
        return {"error": str(e), "companies": []}
