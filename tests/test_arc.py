import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from arc.core import (BANNER, RESIDUAL, RoleFormatError, TimeSplitError, classify,
                      decompose, estimate, json_output, markdown, parse, propose, report, rules)
from arc.fixtures import FIXTURES, generate

VALID = ["inbox-triage.md", "client-coordinator.md", "bookkeeping.md"]


@pytest.fixture
def directory(tmp_path):
    generate(tmp_path)
    return tmp_path


@pytest.mark.parametrize("name,percentages,tools", [
    ("inbox-triage.md", ["70", "20", "10"], ["Fictional mailbox", "Fictional spreadsheet"]),
    ("client-coordinator.md", ["60", "20", "10", "10"], ["Fictional CRM", "Fictional calendar"]),
    ("bookkeeping.md", ["40", "30", "20", "10"], ["Fictional ledger", "Fictional spreadsheet"]),
])
def test_parse(directory, name, percentages, tools):
    role = parse(directory / name)
    assert role["synthetic"] is True
    assert role["weekly_hours"] == "40"
    assert role["tools"] == tools
    assert [r["percent"] for r in role["responsibilities"]] == percentages
    source = FIXTURES[name].splitlines()
    for r in role["responsibilities"]:
        assert source[r["source_line"] - 1] == f"- {r['percent']}%: {r['text']}"


def test_bad_percentages(directory):
    with pytest.raises(TimeSplitError, match="sum to 100"):
        parse(directory / "malformed.md")


@pytest.mark.parametrize("old,new", [
    ("Weekly hours: 40", "Weekly hours: NaN"),
    ("Weekly hours: 40", "Weekly hours: -1"),
    ("Weekly hours: 40", "Weekly hours: nonsense"),
    ("Synthetic: yes", "Synthetic: no"),
    ("- 70%:", "- bad%:"),
    ("## Tools", "## Unknown"),
])
def test_malformed(directory, old, new):
    path = directory / "inbox-triage.md"
    path.write_text(FIXTURES[path.name].replace(old, new), encoding="utf-8")
    with pytest.raises(RoleFormatError):
        parse(path)


def test_decomposition(directory):
    role = parse(directory / "inbox-triage.md")
    tasks = decompose(role)
    assert len(tasks) == 4
    assert [t["percent"] for t in tasks] == ["35", "35", "20", "10"]
    assert tasks[0]["source_line"] == tasks[1]["source_line"] == 8
    assert [t["id"] for t in tasks] == ["T001", "T002", "T003", "T004"]


def test_empty_segment(directory):
    role = parse(directory / "inbox-triage.md")
    role["responsibilities"][0]["text"] += ";"
    with pytest.raises(RoleFormatError, match="empty task"):
        decompose(role)


@pytest.mark.parametrize("text,category,family,term", [
    ("Route structured messages using fixed rules", "automatable", "routine", "route"),
    ("Match structured invoices using exact rules", "automatable", "structured", "exact"),
    ("Negotiate client priorities", "human-judgment", "judgment", "negotiat"),
    ("Route structured messages with discretion", "human-judgment", "judgment", "discretion"),
    ("Draft sensitive replies for human judgment", "hybrid", "judgment", "judgment"),
    ("Prepare summaries", "hybrid", "assistance", "prepare"),
    ("Copy notes", "human-judgment", "routine", "copy"),
])
def test_classify(text, category, family, term):
    task = classify([{"text": text}])[0]
    assert task["classification"] == category
    assert term in task["firing_rules"][family]


@pytest.mark.parametrize("indicator", rules()["judgment"])
def test_judgment_veto(indicator):
    assert classify([{"text": f"Route structured messages with fixed rules and {indicator}"}])[0]["classification"] == "human-judgment"


@pytest.mark.parametrize("name,expected,residual", [
    ("inbox-triage.md", ["21.600000", "30.600000"], ["9.400000", "18.400000"]),
    ("client-coordinator.md", ["3.000000", "4.800000"], ["35.200000", "37.000000"]),
    ("bookkeeping.md", ["13.800000", "21.200000"], ["18.800000", "26.200000"]),
])
def test_hand_calculated_estimates(directory, name, expected, residual):
    role = parse(directory / name)
    model = estimate(role, classify(decompose(role)))
    assert model["savings_hours"] == expected
    assert model["residual_hours"] == residual
    for task in model["tasks"]:
        hours = Decimal(40) * Decimal(task["percent"]) / 100
        fractions = rules()["savings"][task["classification"]]
        assert [Decimal(v) for v in task["savings_hours"]] == [hours * Decimal(f) for f in fractions]
    assert Decimal(expected[1]) <= Decimal(model["eligible_hours_cap"])


@pytest.mark.parametrize("name", VALID)
def test_guardrail(directory, name):
    data = report(parse(directory / name))
    assert data["stays_human"]
    assert data["residual_role"] == RESIDUAL
    assert Decimal(data["residual_hours"][0]) > 0
    assert markdown(data).index("## What stays human") < markdown(data).index("## Tasks")
    assert data["honesty_banner"] == BANNER


def test_all_routine_still_keeps_human(directory):
    role = parse(directory / "inbox-triage.md")
    role["responsibilities"] = [{"text": "Route structured messages using fixed rules", "percent": "100", "source_line": 8}]
    data = report(role)
    assert data["stays_human"]
    assert data["residual_hours"] == ["6.000000", "16.000000"]


@pytest.mark.parametrize("name", VALID)
def test_proposal_order_and_dependencies(directory, name):
    data = report(parse(directory / name))
    phases = data["proposal"]["phases"]
    scores = [Decimal(p["value_over_complexity"]) for p in phases[1:]]
    assert scores == sorted(scores, reverse=True)
    seen = set()
    for phase in phases:
        assert set(phase["dependencies"]) <= seen
        assert phase["risks"] and phase["measure"]
        seen.add(phase["id"])
    expected = {t["id"] for t in data["tasks"] if t["classification"] == "automatable"}
    assert {p["task_id"] for p in phases[1:]} == expected


def test_proposal_tie_break(directory):
    tasks = report(parse(directory / "inbox-triage.md"))["tasks"]
    assert [p["task_id"] for p in propose(list(reversed(tasks)))["phases"][1:]] == ["T001", "T002", "T003"]


def test_fixture_determinism(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    assert generate(first) == generate(second)
    for name in FIXTURES:
        assert (first / name).read_bytes() == (second / name).read_bytes() == FIXTURES[name].encode()
    generate(first)
    assert all((first / n).read_bytes() == (second / n).read_bytes() for n in FIXTURES)


@pytest.mark.parametrize("name", VALID)
@pytest.mark.parametrize("format_name", ["md", "json"])
def test_report_determinism(directory, name, format_name):
    renderer = markdown if format_name == "md" else json_output
    assert renderer(report(parse(directory / name))).encode() == renderer(report(parse(directory / name))).encode()


def run(*args):
    return subprocess.run([sys.executable, "-m", "arc", *map(str, args)], capture_output=True, check=False)


@pytest.mark.parametrize("command,options", [("parse", []), ("parse", ["--decompose"]), ("classify", []), ("estimate", []), ("propose", [])])
def test_cli_smoke(directory, command, options):
    result = run(command, directory / "inbox-triage.md", *options)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)


@pytest.mark.parametrize("name", VALID)
@pytest.mark.parametrize("format_name", ["md", "json"])
def test_end_to_end(directory, name, format_name):
    first = run("report", directory / name, "--format", format_name)
    second = run("report", directory / name, "--format", format_name)
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert BANNER.encode() in first.stdout
    if format_name == "json":
        data = json.loads(first.stdout)
        assert data["stays_human"] and data["proposal"]["phases"]
        assert data["classification_rules"] == rules()
    else:
        assert b"What stays human" in first.stdout


def test_cli_bad_file(directory):
    result = run("parse", directory / "malformed.md")
    assert result.returncode == 2
    assert b"TimeSplitError" in result.stderr


def test_cli_missing_file(directory):
    result = run("parse", directory / "absent.md")
    assert result.returncode == 2
    assert b"FileNotFoundError" in result.stderr


def test_cli_fixtures(tmp_path):
    result = run("fixtures", "--out", tmp_path / "roles")
    assert result.returncode == 0
    assert json.loads(result.stdout)["synthetic"] is True
    assert sorted(p.name for p in (tmp_path / "roles").iterdir()) == sorted(FIXTURES)


def test_no_em_dash_in_project():
    root = Path(__file__).resolve().parents[1]
    for folder in (root / "arc", root / "tests", root / "fixtures"):
        for path in folder.rglob("*"):
            if path.suffix in (".py", ".json", ".md", ".txt"):
                assert chr(0x2014) not in path.read_text(encoding="utf-8"), path
    assert chr(0x2014) not in (root / "README.md").read_text(encoding="utf-8")
