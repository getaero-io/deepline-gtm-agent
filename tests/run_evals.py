#!/usr/bin/env python3
"""
GTM Agent Eval Runner

Invokes the agent with test prompts, captures which tools were called
(both high-level GTM tools and underlying deepline_call tool_ids),
and evaluates pass/fail against expectations defined in tests/evals.yml.

Usage:
    python3 tests/run_evals.py                        # run all evals
    python3 tests/run_evals.py --tags core            # filter by tag
    python3 tests/run_evals.py --eval enrich-person   # run one eval
    python3 tests/run_evals.py --no-live-api          # mock deepline_execute
    python3 tests/run_evals.py --url https://...      # test deployed endpoint
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from unittest.mock import patch

import yaml

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI args
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="GTM Agent Eval Runner")
    p.add_argument("--eval", help="Comma-separated eval IDs to run")
    p.add_argument("--tags", help="Comma-separated tags to filter by (OR)")
    p.add_argument("--runs", type=int, default=1, help="Runs per eval (default 1)")
    p.add_argument("--no-live-api", action="store_true",
                   help="Mock deepline_execute — fast, no API credits consumed")
    p.add_argument("--url", help="Test deployed agent via HTTP instead of direct Python invoke")
    p.add_argument("--verbose", "-v", action="store_true", help="Show full agent output")
    p.add_argument("--output", default="tmp/eval-results.json", help="JSON output path")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Eval loader
# ---------------------------------------------------------------------------

EVALS_FILE = Path(__file__).parent / "evals.yml"


def load_evals(
    eval_ids: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
) -> list[dict]:
    with open(EVALS_FILE) as f:
        data = yaml.safe_load(f)
    evals = data["evals"]

    if eval_ids:
        evals = [e for e in evals if e["id"] in eval_ids]
    if tags:
        evals = [e for e in evals if any(t in e.get("tags", []) for t in tags)]

    return evals


# ---------------------------------------------------------------------------
# Tool call capture
# ---------------------------------------------------------------------------

@dataclass
class ToolCallRecord:
    tool_name: str          # high-level tool name (e.g. "deepline_call", "search_prospects")
    tool_id: Optional[str] = None  # deepline tool_id if deepline_call (e.g. "hubspot_create_contact")
    payload_keys: list[str] = field(default_factory=list)
    result_keys: list[str] = field(default_factory=list)
    error: Optional[str] = None


class ToolCallCapture:
    """Captures tool invocations by patching deepline_execute and recording tool names."""

    def __init__(self):
        self.calls: list[ToolCallRecord] = []
        self._active = False

    @property
    def tool_names_called(self) -> list[str]:
        return [c.tool_name for c in self.calls]

    @property
    def tool_ids_called(self) -> list[str]:
        return [c.tool_id for c in self.calls if c.tool_id]

    def _make_spy(self, original_execute):
        """Wrap deepline_execute to record calls."""
        def spy(operation: str, payload: dict) -> dict:
            try:
                result = original_execute(operation, payload)
            except Exception as e:
                self.calls.append(ToolCallRecord(
                    tool_name="deepline_call",
                    tool_id=operation,
                    payload_keys=list(payload.keys()),
                    error=str(e),
                ))
                raise
            self.calls.append(ToolCallRecord(
                tool_name="deepline_call",
                tool_id=operation,
                payload_keys=list(payload.keys()),
                result_keys=list(result.keys()) if isinstance(result, dict) else [],
            ))
            return result
        return spy


# ---------------------------------------------------------------------------
# Agent runner — direct Python invoke
# ---------------------------------------------------------------------------

async def run_agent_direct(
    prompt: str,
    capture: ToolCallCapture,
    mock_api: bool = False,
    verbose: bool = False,
) -> tuple[str, list[ToolCallRecord]]:
    """
    Invoke the GTM agent directly via Python and return (reply, tool_calls).

    Patches deepline_execute to record all Deepline API calls made during the run.
    When mock_api=True, returns dummy results instead of hitting live APIs.
    """
    # Import here to avoid loading at module level (slow)
    from deepline_gtm_agent.dynamic_tools import load_tool_catalog, make_deepline_call_tool
    from deepline_gtm_agent import create_gtm_agent
    import deepline_gtm_agent.deepline as dl_module
    import deepline_gtm_agent.tools as tools_module

    # Track high-level tool calls by wrapping each tool's underlying function
    high_level_calls: list[str] = []
    original_execute = dl_module.deepline_execute

    def tracking_execute(operation: str, payload: dict) -> dict:
        if mock_api:
            # Return plausible dummy data instead of hitting the API
            result = _mock_response(operation, payload)
            capture.calls.append(ToolCallRecord(
                tool_name="deepline_call",
                tool_id=operation,
                payload_keys=list(payload.keys()),
                result_keys=list(result.keys()),
            ))
            return result
        else:
            try:
                result = original_execute(operation, payload)
            except Exception as e:
                capture.calls.append(ToolCallRecord(
                    tool_name="deepline_call",
                    tool_id=operation,
                    payload_keys=list(payload.keys()),
                    error=str(e),
                ))
                raise
            capture.calls.append(ToolCallRecord(
                tool_name="deepline_call",
                tool_id=operation,
                payload_keys=list(payload.keys()),
                result_keys=list(result.keys()) if isinstance(result, dict) else [],
            ))
            return result

    # Also wrap high-level tool functions to track which ones the agent picked
    def _wrap_tool(fn, name):
        async def async_wrapper(*args, **kwargs):
            high_level_calls.append(name)
            return await fn(*args, **kwargs) if asyncio.iscoroutinefunction(fn) else fn(*args, **kwargs)
        def sync_wrapper(*args, **kwargs):
            high_level_calls.append(name)
            return fn(*args, **kwargs)
        return async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper

    import deepline_gtm_agent.tools as tools_mod
    original_fns = {}
    for fname in ["enrich_person", "waterfall_enrich", "search_prospects", "research_company",
                   "web_research", "verify_email", "find_linkedin", "search_companies"]:
        original_fns[fname] = getattr(tools_mod, fname)
        setattr(tools_mod, fname, _wrap_tool(original_fns[fname], fname))

    try:
        with patch.object(dl_module, "deepline_execute", tracking_execute):
            catalog = load_tool_catalog()
            agent = create_gtm_agent(tool_catalog=catalog)
            result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
            last = result["messages"][-1]
            content = last.content
            if isinstance(content, list):
                reply = "".join(
                    block["text"] if isinstance(block, dict) else str(block)
                    for block in content
                    if not isinstance(block, dict) or block.get("type") == "text"
                )
            else:
                reply = str(content)
    finally:
        for fname, fn in original_fns.items():
            setattr(tools_mod, fname, fn)

    # Merge high-level tool calls into capture
    for name in high_level_calls:
        capture.calls.insert(0, ToolCallRecord(tool_name=name))

    if verbose:
        print(f"\n  Reply: {reply[:300]}")

    return reply, capture.calls


def _mock_response(operation: str, payload: dict) -> dict:
    """Return plausible mock data for a given Deepline operation."""
    if "hubspot" in operation:
        return {"id": "mock-123", "status": "created", "operation": operation}
    if "salesforce" in operation:
        return {"id": "SF-456", "created": True, "operation": operation}
    if "instantly" in operation or "lemlist" in operation or "smartlead" in operation:
        return {"success": True, "campaigns": [{"id": "camp-1", "name": "Test Campaign"}]}
    if "heyreach" in operation:
        return {"campaigns": [{"id": "hr-1", "name": "LinkedIn Campaign"}]}
    if "email" in operation or "hunter" in operation or "zerobounce" in operation or "leadmagic" in operation:
        return {"email": "john@example.com", "status": "valid", "email_status": "valid"}
    if "crustdata" in operation or "apollo" in operation or "dropleads" in operation:
        return {"leads": [{"fullName": "John Doe", "title": "VP Sales", "companyName": "Acme", "linkedinUrl": "https://linkedin.com/in/johndoe"}], "total": 1}
    if "exa" in operation or "research" in operation or "firecrawl" in operation:
        return {"output": "This is a mock research result about the topic.", "data": {"output": "Mock result"}}
    if "phone" in operation:
        return {"phone": "+1-555-123-4567", "status": "valid"}
    return {"result": "mock", "operation": operation, "data": {}}


# ---------------------------------------------------------------------------
# HTTP runner — test deployed endpoint
# ---------------------------------------------------------------------------

async def run_agent_http(
    prompt: str,
    url: str,
    capture: ToolCallCapture,
    verbose: bool = False,
) -> tuple[str, list[ToolCallRecord]]:
    """Call the deployed agent via HTTP POST /chat and return (reply, [])."""
    import httpx
    api_key = os.environ.get("API_KEY", "")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{url.rstrip('/')}/chat",
            json={"messages": [{"role": "user", "content": prompt}]},
            headers=headers,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    reply = resp.json().get("message", "")
    if verbose:
        print(f"\n  Reply: {reply[:300]}")

    # We can't capture tool calls over HTTP — return empty list; tool assertions
    # will be marked as SKIPPED by the caller.
    return reply, []


# ---------------------------------------------------------------------------
# Expectation checker
# ---------------------------------------------------------------------------

@dataclass
class ExpectationResult:
    expectation: str
    passed: bool
    reason: str
    skipped: bool = False


def check_expectations(
    eval_def: dict,
    reply: str,
    calls: list[ToolCallRecord],
) -> list[ExpectationResult]:
    """
    Evaluate all assertions against the agent reply and recorded tool calls.
    Used for direct (non-HTTP) runs where tool call data is available.
    """
    results: list[ExpectationResult] = []
    tool_names = {c.tool_name for c in calls}
    tool_ids = {c.tool_id for c in calls if c.tool_id}
    reply_lower = reply.lower()

    # expect_tools_called: ALL must be present
    for tool in eval_def.get("expect_tools_called", []):
        passed = tool in tool_names or tool in tool_ids
        results.append(ExpectationResult(
            f"tool_called:{tool}",
            passed,
            f"Tool '{tool}' {'called ✓' if passed else 'NOT called ✗'}. Called: {sorted(tool_names | tool_ids)}",
        ))

    # expect_tools_called_any: at least ONE must be present
    any_tools = eval_def.get("expect_tools_called_any", [])
    if any_tools:
        passed = any(t in tool_names or t in tool_ids for t in any_tools)
        results.append(ExpectationResult(
            f"tool_called_any:{any_tools}",
            passed,
            f"At least one of {any_tools} {'called ✓' if passed else 'NOT called ✗'}. Called: {sorted(tool_names | tool_ids)}",
        ))

    # expect_tool_ids_called: specific deepline tool_ids, ALL must be present
    for tid in eval_def.get("expect_tool_ids_called", []):
        passed = tid in tool_ids
        results.append(ExpectationResult(
            f"tool_id_called:{tid}",
            passed,
            f"Tool ID '{tid}' {'called ✓' if passed else 'NOT called ✗'}. IDs called: {sorted(tool_ids)}",
        ))

    # expect_tool_ids_called_any: at least ONE tool ID must be present
    any_ids = eval_def.get("expect_tool_ids_called_any", [])
    if any_ids:
        passed = any(tid in tool_ids for tid in any_ids)
        results.append(ExpectationResult(
            f"tool_id_called_any:{any_ids}",
            passed,
            f"At least one of {any_ids} {'called ✓' if passed else 'NOT called ✗'}. IDs: {sorted(tool_ids)}",
        ))

    # expect_tools_not_called: none of these should appear
    for tool in eval_def.get("expect_tools_not_called", []):
        passed = tool not in tool_names and tool not in tool_ids
        results.append(ExpectationResult(
            f"tool_not_called:{tool}",
            passed,
            f"Tool '{tool}' {'absent ✓' if passed else 'unexpectedly called ✗'}",
        ))

    # expect_response_contains: ALL keywords must appear in reply (case-insensitive)
    for kw in eval_def.get("expect_response_contains", []):
        passed = kw.lower() in reply_lower
        results.append(ExpectationResult(
            f"response_contains:{kw}",
            passed,
            f"Response {'contains' if passed else 'missing'} '{kw}' {'✓' if passed else '✗'}",
        ))

    # expect_response_contains_any: at least ONE keyword must appear
    any_kws = eval_def.get("expect_response_contains_any", [])
    if any_kws:
        passed = any(kw.lower() in reply_lower for kw in any_kws)
        results.append(ExpectationResult(
            f"response_contains_any:{any_kws}",
            passed,
            f"Response {'contains one of' if passed else 'missing all of'} {any_kws} {'✓' if passed else '✗'}",
        ))

    # expect_response_not_contains: ALL phrases must be absent from reply (case-insensitive)
    for phrase in eval_def.get("expect_response_not_contains", []):
        passed = phrase.lower() not in reply_lower
        results.append(ExpectationResult(
            f"response_not_contains:{phrase}",
            passed,
            f"Response {'correctly absent' if passed else 'BAD: contains'} '{phrase}' {'✓' if passed else '✗'}",
        ))

    # expect_response_matches_regex: ALL patterns must match somewhere in reply
    for pattern in eval_def.get("expect_response_matches_regex", []):
        try:
            matched = bool(re.search(pattern, reply, re.IGNORECASE))
        except re.error as exc:
            matched = False
        results.append(ExpectationResult(
            f"response_matches_regex:{pattern}",
            matched,
            f"Regex '{pattern}' {'matched ✓' if matched else 'did not match ✗'}",
        ))

    return results


def check_expectations_http(
    eval_def: dict,
    reply: str,
) -> list[ExpectationResult]:
    """
    Evaluate assertions for HTTP mode runs.

    Response assertions (contains, not_contains, regex) are checked normally.
    Tool assertions (expect_tools_called, expect_tool_ids_called, etc.) are
    marked as SKIPPED because tool call data is not available over HTTP.
    """
    results: list[ExpectationResult] = []
    reply_lower = reply.lower()

    # --- Response assertions — fully evaluated ---

    # expect_response_contains: ALL keywords must appear
    for kw in eval_def.get("expect_response_contains", []):
        passed = kw.lower() in reply_lower
        results.append(ExpectationResult(
            f"response_contains:{kw}",
            passed,
            f"Response {'contains' if passed else 'missing'} '{kw}' {'✓' if passed else '✗'}",
            skipped=False,
        ))

    # expect_response_contains_any: at least ONE keyword must appear
    any_kws = eval_def.get("expect_response_contains_any", [])
    if any_kws:
        passed = any(kw.lower() in reply_lower for kw in any_kws)
        results.append(ExpectationResult(
            f"response_contains_any:{any_kws}",
            passed,
            f"Response {'contains one of' if passed else 'missing all of'} {any_kws} {'✓' if passed else '✗'}",
            skipped=False,
        ))

    # expect_response_not_contains: ALL phrases must be absent
    for phrase in eval_def.get("expect_response_not_contains", []):
        passed = phrase.lower() not in reply_lower
        results.append(ExpectationResult(
            f"response_not_contains:{phrase}",
            passed,
            f"Response {'correctly absent' if passed else 'BAD: contains'} '{phrase}' {'✓' if passed else '✗'}",
            skipped=False,
        ))

    # expect_response_matches_regex: ALL patterns must match
    for pattern in eval_def.get("expect_response_matches_regex", []):
        try:
            matched = bool(re.search(pattern, reply, re.IGNORECASE))
        except re.error:
            matched = False
        results.append(ExpectationResult(
            f"response_matches_regex:{pattern}",
            matched,
            f"Regex '{pattern}' {'matched ✓' if matched else 'did not match ✗'}",
            skipped=False,
        ))

    # --- Tool assertions — SKIPPED (can't verify over HTTP) ---

    for tool in eval_def.get("expect_tools_called", []):
        results.append(ExpectationResult(
            f"tool_called:{tool}",
            True,
            f"SKIPPED — tool routing not verifiable over HTTP",
            skipped=True,
        ))

    any_tools = eval_def.get("expect_tools_called_any", [])
    if any_tools:
        results.append(ExpectationResult(
            f"tool_called_any:{any_tools}",
            True,
            f"SKIPPED — tool routing not verifiable over HTTP",
            skipped=True,
        ))

    for tid in eval_def.get("expect_tool_ids_called", []):
        results.append(ExpectationResult(
            f"tool_id_called:{tid}",
            True,
            f"SKIPPED — tool routing not verifiable over HTTP",
            skipped=True,
        ))

    any_ids = eval_def.get("expect_tool_ids_called_any", [])
    if any_ids:
        results.append(ExpectationResult(
            f"tool_id_called_any:{any_ids}",
            True,
            f"SKIPPED — tool routing not verifiable over HTTP",
            skipped=True,
        ))

    for tool in eval_def.get("expect_tools_not_called", []):
        results.append(ExpectationResult(
            f"tool_not_called:{tool}",
            True,
            f"SKIPPED — tool routing not verifiable over HTTP",
            skipped=True,
        ))

    return results


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

@dataclass
class EvalRunResult:
    eval_id: str
    run: int
    duration_s: float
    passed: int
    total: int
    skipped: int
    expectations: list[ExpectationResult]
    reply_preview: str
    tool_calls: list[str]
    tool_ids: list[str]
    error: Optional[str] = None

    @property
    def pass_rate(self) -> str:
        return f"{self.passed}/{self.total}"


async def run_eval(
    eval_def: dict,
    run_num: int = 1,
    mock_api: bool = False,
    http_url: Optional[str] = None,
    verbose: bool = False,
) -> EvalRunResult:
    eval_id = eval_def["id"]
    prompt = eval_def["prompt"].strip()
    t0 = time.time()
    error = None
    reply = ""
    calls: list[ToolCallRecord] = []

    try:
        capture = ToolCallCapture()
        if http_url:
            reply, calls = await run_agent_http(prompt, http_url, capture, verbose=verbose)
        else:
            reply, calls = await run_agent_direct(prompt, capture, mock_api=mock_api, verbose=verbose)
    except Exception as e:
        error = str(e)
        print(f"    ERROR: {e}")

    duration = time.time() - t0

    if http_url:
        # HTTP mode: response assertions checked, tool assertions skipped
        expectations = check_expectations_http(eval_def, reply)
    else:
        # Direct mode: all assertions fully checked
        expectations = check_expectations(eval_def, reply, calls)

    # Count only non-skipped expectations toward pass/fail totals
    active = [e for e in expectations if not e.skipped]
    skipped_count = sum(1 for e in expectations if e.skipped)
    passed_count = sum(1 for e in active if e.passed)

    return EvalRunResult(
        eval_id=eval_id,
        run=run_num,
        duration_s=duration,
        passed=passed_count,
        total=len(active),
        skipped=skipped_count,
        expectations=expectations,
        reply_preview=reply[:200],
        tool_calls=[c.tool_name for c in calls],
        tool_ids=[c.tool_id for c in calls if c.tool_id],
        error=error,
    )


def print_result(result: EvalRunResult, verbose: bool = False) -> None:
    active_total = result.total
    if result.error:
        status = "💥 ERR "
    elif active_total == 0:
        status = "⊘  SKIP"
    elif result.passed == active_total:
        status = "✅ PASS"
    elif result.passed > 0:
        status = "⚠️  PART"
    else:
        status = "❌ FAIL"

    tag = f"[{result.eval_id}]"
    rate = f"{result.pass_rate}" if active_total else "n/a"
    skip_note = f" +{result.skipped}sk" if result.skipped else ""
    dur = f"{result.duration_s:.1f}s"
    tool_str = ",".join(dict.fromkeys(result.tool_calls))[:50] if result.tool_calls else "—"
    print(f"  {status} {tag:<42} {rate}{skip_note:<10} {dur:<8} tools: {tool_str}")

    if verbose or result.passed < active_total:
        for exp in result.expectations:
            if exp.skipped:
                mark = "  ⊘"
            elif exp.passed:
                mark = "  ✓"
            else:
                mark = "  ✗"
            print(f"       {mark} {exp.reason}")
        if result.reply_preview:
            print(f"       reply: {result.reply_preview[:120]}…")


def print_summary(results: list[EvalRunResult]) -> None:
    active_results = [r for r in results if not r.error]
    total_pass = sum(r.passed for r in results)
    total_exp = sum(r.total for r in results)
    total_skipped = sum(r.skipped for r in results)
    full_passes = sum(1 for r in results if r.passed == r.total and not r.error and r.total > 0)
    avg_dur = sum(r.duration_s for r in results) / len(results) if results else 0

    skip_note = (
        f"   ({total_skipped} assertions skipped — run locally to verify tool routing)"
        if total_skipped else ""
    )

    print("\n" + "=" * 70)
    print(f"  SUMMARY: {full_passes}/{len(results)} evals fully passed   "
          f"({total_pass}/{total_exp} expectations){skip_note}   avg {avg_dur:.1f}s/eval")
    print("=" * 70)

    # Failures — only non-skipped failed assertions
    failed = [r for r in results if r.passed < r.total or r.error]
    if failed:
        print("\n  FAILURES:")
        for r in failed:
            failed_exps = [e for e in r.expectations if not e.passed and not e.skipped]
            for exp in failed_exps:
                print(f"    [{r.eval_id}] {exp.reason}")
    print()


async def main() -> int:
    args = parse_args()

    eval_ids = [x.strip() for x in args.eval.split(",")] if args.eval else None
    tags = [x.strip() for x in args.tags.split(",")] if args.tags else None
    evals = load_evals(eval_ids=eval_ids, tags=tags)

    if not evals:
        print("No evals matched. Check --eval / --tags.")
        return 1

    mode = f"HTTP:{args.url}" if args.url else ("mock" if args.no_live_api else "live API")
    print(f"\n{'='*70}")
    print(f"  GTM Agent Evals — {len(evals)} evals × {args.runs} run(s) — mode: {mode}")
    print(f"{'='*70}\n")

    all_results: list[EvalRunResult] = []

    for eval_def in evals:
        print(f"  [{eval_def['id']}] {eval_def['prompt'].strip()[:60]}…")
        for run_num in range(1, args.runs + 1):
            result = await run_eval(
                eval_def,
                run_num=run_num,
                mock_api=args.no_live_api,
                http_url=args.url,
                verbose=args.verbose,
            )
            print_result(result, verbose=args.verbose)
            all_results.append(result)
        print()

    print_summary(all_results)

    # Write JSON output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps([
        {
            "eval_id": r.eval_id,
            "run": r.run,
            "duration_s": r.duration_s,
            "passed": r.passed,
            "total": r.total,
            "skipped": r.skipped,
            "pass_rate": r.pass_rate,
            "tool_calls": r.tool_calls,
            "tool_ids": r.tool_ids,
            "expectations": [
                {
                    "exp": e.expectation,
                    "passed": e.passed,
                    "reason": e.reason,
                    "skipped": e.skipped,
                }
                for e in r.expectations
            ],
            "reply_preview": r.reply_preview,
            "error": r.error,
        }
        for r in all_results
    ], indent=2))
    print(f"  Results written to {output_path}")

    # Exit 1 if any eval has ALL non-skipped expectations failed (total > 0 and passed == 0)
    fully_failed = [r for r in all_results if r.total > 0 and r.passed == 0]
    return 1 if fully_failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
