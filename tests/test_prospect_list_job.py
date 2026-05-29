from __future__ import annotations

import csv
import json
from pathlib import Path

import deepline_gtm_agent.tools as tools


class Completed:
    def __init__(self, args: list[str], stdout: str = "{}", returncode: int = 0):
        self.args = args
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def _write_input_csv(path: Path) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["first_name", "last_name", "domain"])
        writer.writeheader()
        writer.writerow({"first_name": "Ada", "last_name": "Lovelace", "domain": "example.com"})


def test_batch_enrich_honors_output_dir_and_pilots_rows(tmp_path, monkeypatch):
    input_csv = tmp_path / "leads.csv"
    _write_input_csv(input_csv)
    commands: list[list[str]] = []

    def fake_run(cmd, capture_output, text, timeout):
        commands.append(cmd)
        if cmd[:3] == ["deepline", "csv", "show"]:
            return Completed(cmd, stdout=json.dumps({"row_count": 1, "columns": ["email"]}))
        output_path = Path(cmd[cmd.index("--output") + 1])
        output_path.write_text("email\nada@example.com\n")
        return Completed(cmd, stdout=json.dumps({"ok": True}))

    monkeypatch.setattr(tools.subprocess, "run", fake_run)

    result = tools.batch_enrich(
        input_csv=str(input_csv),
        columns=[{"alias": "email", "tool": "hunter_email_finder", "payload": {"domain": "{{domain}}"}}],
        output_dir=str(tmp_path / "job"),
        rows="0:1",
    )

    assert result["pilot_done"] is True
    assert result["output_csv"] == str(tmp_path / "job" / "leads_enriched.csv")
    enrich_cmd = commands[0]
    assert enrich_cmd[:2] == ["deepline", "enrich"]
    assert enrich_cmd[enrich_cmd.index("--rows") + 1] == "0:1"


def test_build_prospect_list_job_creates_seed_csv_and_pilot(tmp_path, monkeypatch):
    commands: list[list[str]] = []

    def fake_execute(operation: str, payload: dict) -> dict:
        assert operation == "exa_research"
        assert "Return JSON only" in payload["instructions"]
        return {
            "data": {
                "output": json.dumps([
                    {
                        "company_name": "Acme AI",
                        "domain": "acme.ai",
                        "industry": "AI infrastructure",
                        "evidence_url": "https://example.com/acme",
                    },
                    {
                        "name": "Beta Data",
                        "website": "https://beta.example",
                        "industry": "Data tooling",
                    },
                ])
            }
        }

    def fake_run(cmd, capture_output, text, timeout):
        commands.append(cmd)
        if cmd[:3] == ["deepline", "csv", "show"]:
            return Completed(cmd, stdout=json.dumps({"row_count": 1, "columns": ["contacts"]}))
        output_path = Path(cmd[cmd.index("--output") + 1])
        output_path.write_text("company_name,contacts\nAcme AI,Jane Doe\n")
        return Completed(cmd, stdout=json.dumps({"ok": True}))

    monkeypatch.setattr(tools, "deepline_execute", fake_execute)
    monkeypatch.setattr(tools.subprocess, "run", fake_run)

    result = tools.build_prospect_list_job(
        criteria="AI infrastructure companies in the US",
        target_count=2,
        persona="VP Engineering",
        output_dir=str(tmp_path / "prospect-job"),
    )

    assert result["job_status"] == "pilot_ready"
    assert result["target_count"] == 2
    assert result["seed_target"] == 3
    seed_csv = Path(result["seed_csv"])
    assert seed_csv.exists()
    assert "Acme AI" in seed_csv.read_text()
    assert (tmp_path / "prospect-job" / "prospect_job_plan.json").exists()

    enrich_cmd = commands[0]
    assert enrich_cmd[:2] == ["deepline", "enrich"]
    assert "--rows" in enrich_cmd
    assert enrich_cmd[enrich_cmd.index("--rows") + 1] == "0:1"
    with_arg = json.loads(enrich_cmd[enrich_cmd.index("--with") + 1])
    assert with_arg["tool"] == "exa_people_search"
    assert "VP Engineering" in with_arg["payload"]["query"]
    assert Path(result["pilot"]["output_csv"]).parent.name == "pilot"


def test_build_prospect_list_job_seed_only_without_persona(tmp_path):
    result = tools.build_prospect_list_job(
        criteria="Series B fintech",
        target_count=1,
        seed_rows=[{"company_name": "FinCo", "domain": "finco.com"}],
        output_dir=str(tmp_path / "seed-only"),
    )

    assert result["job_status"] == "seed_ready"
    assert result["seed_summary"]["row_count"] == 1
    assert "persona" in result["next_step"]


def test_build_prospect_list_job_full_run_reuses_seed_csv_without_rediscovery(tmp_path, monkeypatch):
    seed_csv = tmp_path / "seed_companies.csv"
    with seed_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["company_name", "domain"])
        writer.writeheader()
        writer.writerow({"company_name": "Acme AI", "domain": "acme.ai"})

    commands: list[list[str]] = []

    def fail_execute(operation: str, payload: dict) -> dict:
        raise AssertionError(f"unexpected rediscovery call: {operation}")

    def fake_run(cmd, capture_output, text, timeout):
        commands.append(cmd)
        if cmd[:3] == ["deepline", "csv", "show"]:
            return Completed(cmd, stdout=json.dumps({"row_count": 1, "columns": ["contacts"]}))
        output_path = Path(cmd[cmd.index("--output") + 1])
        output_path.write_text("company_name,contacts\nAcme AI,Jane Doe\n")
        return Completed(cmd, stdout=json.dumps({"ok": True}))

    monkeypatch.setattr(tools, "deepline_execute", fail_execute)
    monkeypatch.setattr(tools.subprocess, "run", fake_run)

    result = tools.build_prospect_list_job(
        criteria="AI infrastructure companies in the US",
        target_count="1",
        persona="VP Engineering",
        seed_csv_path=str(seed_csv),
        run_full=True,
    )

    assert result["job_status"] == "complete"
    assert result["seed_csv"] == str(seed_csv)
    assert result["pilot"]["skipped"] is True
    assert result["output_csv"] == str(tmp_path / "seed_companies_enriched.csv")

    enrich_cmds = [cmd for cmd in commands if cmd[:2] == ["deepline", "enrich"]]
    assert len(enrich_cmds) == 1
    assert "--rows" not in enrich_cmds[0]


def test_build_prospect_list_job_blocks_full_run_when_pilot_fails(tmp_path, monkeypatch):
    commands: list[list[str]] = []

    def fake_run(cmd, capture_output, text, timeout):
        commands.append(cmd)
        return Completed(cmd, stdout="", returncode=2)

    monkeypatch.setattr(tools.subprocess, "run", fake_run)

    result = tools.build_prospect_list_job(
        criteria="AI infrastructure companies in the US",
        target_count=1,
        persona="VP Engineering",
        seed_rows=[{"company_name": "Acme AI", "domain": "acme.ai"}],
        output_dir=str(tmp_path / "job"),
        run_full=True,
    )

    assert result["job_status"] == "pilot_error"
    assert "full_run" not in result
    assert len([cmd for cmd in commands if cmd[:2] == ["deepline", "enrich"]]) == 1


def test_build_prospect_list_job_requires_approved_seed_csv_for_full_run(tmp_path, monkeypatch):
    commands: list[list[str]] = []

    def fake_run(cmd, capture_output, text, timeout):
        commands.append(cmd)
        if cmd[:3] == ["deepline", "csv", "show"]:
            return Completed(cmd, stdout=json.dumps({"row_count": 1, "columns": ["contacts"]}))
        output_path = Path(cmd[cmd.index("--output") + 1])
        output_path.write_text("company_name,contacts\nAcme AI,Jane Doe\n")
        return Completed(cmd, stdout=json.dumps({"ok": True}))

    monkeypatch.setattr(tools.subprocess, "run", fake_run)

    result = tools.build_prospect_list_job(
        criteria="AI infrastructure companies in the US",
        target_count=1,
        persona="VP Engineering",
        seed_rows=[{"company_name": "Acme AI", "domain": "acme.ai"}],
        output_dir=str(tmp_path / "job"),
        run_full=True,
    )

    assert result["job_status"] == "approval_required"
    assert "full_run" not in result
    enrich_cmds = [cmd for cmd in commands if cmd[:2] == ["deepline", "enrich"]]
    assert len(enrich_cmds) == 1
    assert enrich_cmds[0][enrich_cmds[0].index("--rows") + 1] == "0:1"


def test_batch_enrich_normalizes_legacy_tool_id_column(tmp_path, monkeypatch):
    input_csv = tmp_path / "leads.csv"
    _write_input_csv(input_csv)
    commands: list[list[str]] = []

    def fake_run(cmd, capture_output, text, timeout):
        commands.append(cmd)
        if cmd[:3] == ["deepline", "csv", "show"]:
            return Completed(cmd, stdout=json.dumps({"row_count": 1, "columns": ["email"]}))
        output_path = Path(cmd[cmd.index("--output") + 1])
        output_path.write_text("email\nada@example.com\n")
        return Completed(cmd, stdout=json.dumps({"ok": True}))

    monkeypatch.setattr(tools.subprocess, "run", fake_run)

    tools.batch_enrich(
        input_csv=str(input_csv),
        columns=[{"tool_id": "hunter_email_finder", "payload": {"domain": "{{domain}}"}}],
        output_dir=str(tmp_path / "job"),
    )

    with_arg = json.loads(commands[0][commands[0].index("--with") + 1])
    assert with_arg["tool"] == "hunter_email_finder"
    assert with_arg["alias"] == "hunter_email_finder"
