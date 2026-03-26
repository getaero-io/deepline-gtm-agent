"""
Deepline operations exposed as Deep Agents-compatible tool functions.

Each function follows the Deep Agents convention:
- Plain Python function with a clear docstring
- Type-annotated parameters (auto-generate the tool schema)
- Returns a dict or str that the agent can reason about
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
    Enrich a person's contact data: work email, phone, job title, LinkedIn.

    Runs a waterfall across Apollo, Hunter, and Crustdata.
    At least one of linkedin_url, email, or (first_name + last_name + company) is required.

    Returns a dict with: email, phone, linkedin_url, title, company, location.
    """
    if not any([linkedin_url, email, (first_name and last_name)]):
        return {"error": "Provide linkedin_url, email, or first_name + last_name."}

    # Apollo people match — best for name + company lookup
    apollo_payload: dict = {}
    if linkedin_url:
        apollo_payload["linkedin_url"] = linkedin_url
    if email:
        apollo_payload["email"] = email
    if first_name:
        apollo_payload["first_name"] = first_name
    if last_name:
        apollo_payload["last_name"] = last_name
    if company_domain:
        apollo_payload["domain"] = company_domain
    if company_name:
        apollo_payload["organization_name"] = company_name

    try:
        result = deepline_execute("apollo_people_match", apollo_payload)
        person = result.get("person", result)
        if person and (person.get("email") or person.get("linkedin_url")):
            return {
                "provider": "apollo",
                "name": f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
                "email": person.get("email"),
                "phone": person.get("phone_numbers", [{}])[0].get("sanitized_number") if person.get("phone_numbers") else None,
                "title": person.get("title"),
                "company": person.get("organization_name"),
                "linkedin_url": person.get("linkedin_url"),
                "location": person.get("city"),
            }
    except Exception:
        pass

    # Hunter combined find as fallback
    if company_domain and (first_name or last_name):
        try:
            result = deepline_execute("hunter_combined_find", {
                "domain": company_domain,
                "first_name": first_name or "",
                "last_name": last_name or "",
            })
            if result.get("email"):
                return {
                    "provider": "hunter",
                    "email": result.get("email"),
                    "name": f"{first_name or ''} {last_name or ''}".strip(),
                    "company": company_name or company_domain,
                    "linkedin_url": linkedin_url,
                }
        except Exception:
            pass

    # Crustdata people enrichment — good for LinkedIn-based lookups
    if linkedin_url:
        try:
            result = deepline_execute("crustdata_people_enrich", {"linkedin_url": linkedin_url})
            if result:
                return {"provider": "crustdata", **result}
        except Exception:
            pass

    return {"error": "Could not enrich contact — try providing more identifiers."}


# ---------------------------------------------------------------------------
# Prospect search
# ---------------------------------------------------------------------------


def search_prospects(
    job_title: Optional[str] = None,
    job_level: Optional[str] = None,
    company_name: Optional[str] = None,
    company_domain: Optional[str] = None,
    person_location: Optional[str] = None,
    company_industry: Optional[str] = None,
    company_size_min: Optional[int] = None,
    company_size_max: Optional[int] = None,
    limit: int = 10,
) -> dict:
    """
    Search for people (prospects) matching ICP criteria.

    job_level accepted values: owner, founder, c_suite, vp, director, manager, individual_contributor.
    company_size_min / company_size_max: integer employee counts (e.g. 200, 500).

    Returns a list of people with name, title, company, LinkedIn URL, and email (when available).
    """
    payload: dict = {"per_page": min(limit, 100), "include_similar_titles": True}

    if job_title:
        payload["person_titles"] = [job_title]
    if job_level:
        payload["person_seniorities"] = [job_level]
    if company_domain:
        payload["q_organization_domains_list"] = [company_domain]
    if person_location:
        payload["person_locations"] = [person_location]
    if company_size_min or company_size_max:
        lo = company_size_min or 1
        hi = company_size_max or 100_000
        payload["organization_num_employees_ranges"] = [f"{lo},{hi}"]
    if company_industry:
        payload["q_keywords"] = company_industry

    result = deepline_execute("apollo_search_people", payload)
    people = result.get("people", [])[:limit]
    return {
        "provider": "apollo",
        "count": len(people),
        "prospects": [
            {
                "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "title": p.get("title"),
                "company": p.get("organization_name"),
                "linkedin_url": p.get("linkedin_url"),
                "email": p.get("email"),
                "location": p.get("city"),
            }
            for p in people
        ],
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

    Fetches firmographic data from Apollo and Crustdata.
    Provide domain (e.g. "stripe.com") or company_name.
    """
    if not domain and not company_name:
        return {"error": "Provide domain or company_name."}

    payload: dict = {}
    if domain:
        payload["domain"] = domain
    if company_name:
        payload["name"] = company_name

    try:
        result = deepline_execute("apollo_organization_enrich", payload)
        org = result.get("organization", result)
        if org and org.get("name"):
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
                "technologies": org.get("technology_names", [])[:10],
            }
    except Exception:
        pass

    # Crustdata fallback
    if domain:
        try:
            result = deepline_execute("crustdata_company_enrichment", {"domain": domain})
            if result:
                return {"provider": "crustdata", **result}
        except Exception:
            pass

    return {"error": f"Could not find company data for {domain or company_name}"}


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
        status = result.get("status", "unknown")
        return {
            "provider": "leadmagic",
            "email": email,
            "valid": status == "valid",
            "status": status,
            "safe_to_send": status == "valid",
        }
    except Exception:
        pass

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

    Returns: {"linkedin_url": str, "confidence": str}
    """
    apollo_payload: dict = {
        "first_name": first_name,
        "last_name": last_name,
    }
    if company_name:
        apollo_payload["organization_name"] = company_name
    if company_domain:
        apollo_payload["organization_domain_name"] = company_domain

    try:
        result = deepline_execute("apollo_people_match", apollo_payload)
        person = result.get("person", {})
        linkedin = person.get("linkedin_url", "")
        if linkedin:
            return {"linkedin_url": linkedin, "confidence": "high", "provider": "apollo"}
    except Exception:
        pass

    # Apollo search fallback
    search_payload: dict = {
        "per_page": 1,
    }
    if company_name:
        search_payload["organization_names"] = [company_name]

    try:
        result = deepline_execute("apollo_search_people", search_payload)
        people = result.get("people", [])
        if people and people[0].get("linkedin_url"):
            return {
                "linkedin_url": people[0]["linkedin_url"],
                "confidence": "medium",
                "provider": "apollo_search",
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
    keywords: Optional[str] = None,
    limit: int = 25,
) -> dict:
    """
    Build a list of companies matching ICP criteria.

    Searches Apollo for companies by industry, location, headcount range, or keyword.
    Use this to build target account lists before finding contacts.

    headcount_min / headcount_max: integer employee counts (e.g. 200, 500).
    Returns a list of companies with name, domain, headcount, industry, and description.
    """
    payload: dict = {"per_page": min(limit, 25)}

    if location:
        payload["organization_locations"] = [location]
    if headcount_min or headcount_max:
        lo = headcount_min or 1
        hi = headcount_max or 100_000
        payload["organization_num_employees_ranges"] = [f"{lo},{hi}"]
    if keywords:
        payload["q_organization_keyword_tags"] = [keywords]
    if industry:
        payload["q_organization_keyword_tags"] = [*(payload.get("q_organization_keyword_tags") or []), industry]

    result = deepline_execute("apollo_company_search", payload)
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
